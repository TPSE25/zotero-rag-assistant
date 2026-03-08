import { ChatTitleMessage, RagClient, Source } from "./ragClient";
import { getString } from "../utils/locale";
import { ChatDB, ChatMessage, ChatSession } from "./ragStorage";
import { showZoteroSource } from "./openSource";
import { assert } from "../utils/assert";

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const escapeHtmlAttribute = (value: string): string =>
  escapeHtml(value).replace(/`/g, "&#96;");

const safeHref = (rawHref: string): string | null => {
  const href = rawHref.trim();
  if (!href) return null;
  if (href.startsWith("/")) return href;

  try {
    const parsed = new URL(href);
    if (
      parsed.protocol === "http:" ||
      parsed.protocol === "https:" ||
      parsed.protocol === "mailto:" ||
      parsed.protocol === "zotero:"
    ) {
      return href;
    }
  } catch {
    return null;
  }

  return null;
};

const formatSourcePages = (pages?: number[]): string => {
  if (!pages?.length) return "";
  const sorted = [...new Set(pages)].sort((a, b) => a - b);
  const ranges: string[] = [];
  let start = sorted[0];
  let prev = sorted[0];

  for (let i = 1; i < sorted.length; i++) {
    const page = sorted[i];
    if (page === prev + 1) {
      prev = page;
      continue;
    }
    ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
    start = page;
    prev = page;
  }

  ranges.push(start === prev ? `${start}` : `${start}-${prev}`);
  return ` (pp. ${ranges.join(", ")})`;
};

const renderInlineMarkdown = (
  raw: string,
  sourceById: Map<string, Source>,
): string => {
  const tokenToHtml = new Map<string, string>();
  let counter = 0;

  const addToken = (html: string): string => {
    const token = `@@MDTOKINLINE${counter++}@@`;
    tokenToHtml.set(token, html);
    return token;
  };

  let text = raw;

  text = text.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, label, href) => {
    const safe = safeHref(href);
    if (!safe) return addToken(`${escapeHtml(label)} (${escapeHtml(href)})`);
    return addToken(
      `<a href="${escapeHtmlAttribute(safe)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`,
    );
  });

  text = text.replace(/`([^`\n]+)`/g, (_m, code) =>
    addToken(`<code>${escapeHtml(code)}</code>`),
  );

  text = text.replace(/\[(S\d+)\]/gi, (_m, sourceId) => {
    const normalizedId = String(sourceId).toUpperCase();
    const source = sourceById.get(normalizedId);
    if (!source) return `[${sourceId}]`;
    const tooltip = `${source.id}: ${source.filename}${formatSourcePages(source.pages)}`;
    return addToken(
      `<a href="#" class="rag-inline-source" data-source-id="${escapeHtmlAttribute(source.id)}" title="${escapeHtmlAttribute(tooltip)}">[${escapeHtml(source.id)}]</a>`,
    );
  });

  let html = escapeHtml(text);
  html = html
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
    .replace(/_([^_\n]+)_/g, "<em>$1</em>");

  for (const [token, tokenHtml] of tokenToHtml.entries()) {
    html = html.replaceAll(token, tokenHtml);
  }

  return html;
};

const renderAssistantMarkdown = (
  rawContent: string,
  sources: Source[] = [],
): string => {
  const fencedBlocks = new Map<string, string>();
  let fenceCounter = 0;
  const normalized = rawContent.replace(/\r\n?/g, "\n");

  const withFenceTokens = normalized.replace(
    /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g,
    (_m, lang, code) => {
      const safeToken = `@@MDTOKBLOCK${fenceCounter++}@@`;
      const classAttr = lang
        ? ` class="language-${escapeHtmlAttribute(String(lang))}"`
        : "";
      const cleanCode = String(code).replace(/\n$/, "");
      fencedBlocks.set(
        safeToken,
        `<pre class="rag-code-block"><code${classAttr}>${escapeHtml(cleanCode)}</code></pre>`,
      );
      return safeToken;
    },
  );

  const lines = withFenceTokens.split("\n");
  const out: string[] = [];
  let inUl = false;
  let inOl = false;
  const sourceById = new Map<string, Source>();
  for (const source of sources) {
    sourceById.set(source.id.toUpperCase(), source);
  }

  const renderWithSourceLinks = (text: string): string =>
    renderInlineMarkdown(text, sourceById);

  const closeLists = () => {
    if (inUl) {
      out.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      out.push("</ol>");
      inOl = false;
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      closeLists();
      continue;
    }

    if (fencedBlocks.has(trimmed)) {
      closeLists();
      out.push(trimmed);
      continue;
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      closeLists();
      const level = heading[1].length;
      out.push(`<h${level}>${renderWithSourceLinks(heading[2])}</h${level}>`);
      continue;
    }

    const quote = trimmed.match(/^>\s?(.*)$/);
    if (quote) {
      closeLists();
      out.push(`<blockquote>${renderWithSourceLinks(quote[1])}</blockquote>`);
      continue;
    }

    const ul = trimmed.match(/^[-*]\s+(.+)$/);
    if (ul) {
      if (inOl) {
        out.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        out.push("<ul>");
        inUl = true;
      }
      out.push(`<li>${renderWithSourceLinks(ul[1])}</li>`);
      continue;
    }

    const ol = trimmed.match(/^\d+\.\s+(.+)$/);
    if (ol) {
      if (inUl) {
        out.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        out.push("<ol>");
        inOl = true;
      }
      out.push(`<li>${renderWithSourceLinks(ol[1])}</li>`);
      continue;
    }

    closeLists();
    out.push(`<p>${renderWithSourceLinks(trimmed)}</p>`);
  }

  closeLists();

  let html = out.join("\n");
  for (const [token, tokenHtml] of fencedBlocks.entries()) {
    html = html.replaceAll(token, tokenHtml);
  }
  return html;
};

export class RagSection {
  private static ragClient = new RagClient();

  private static chatDB: ChatDB | null = null;

  static register() {
    Zotero.ItemPaneManager.registerSection({
      paneID: "rag-assistant",
      pluginID: addon.data.config.addonID,
      header: {
        l10nID: "rag-section-header",
        icon: "chrome://rag/content/icons/search.svg",
      },
      sidenav: {
        l10nID: "rag-section-sidenav",
        icon: "chrome://rag/content/icons/search.svg",
      },
      bodyXHTML: `
        <html:style>
            #rag-root {
              padding: 10px;
              height: 100%;
              display: flex;
              flex-direction: column;
              gap: 8px;
              background-color: Canvas;
              color: CanvasText;
              min-width: 0;
              max-width: 100%;
              overflow-x: hidden;
            }
        
            #rag-tabs-row {
              display: grid;
              grid-template-columns: minmax(0, 1fr) auto;
              column-gap: 6px;
              align-items: center;

              width: 100%;
              max-width: 100%;
              min-width: 0;
              overflow: hidden;
            }
        
            #rag-tabs {
              display: flex;
              flex-direction: row;
              gap: 6px;
              min-width: 0;
              max-width: 100%;
              overflow-x: auto;
              overflow-y: hidden;
              white-space: nowrap;
            }

            #rag-new-chat {
              flex: 0 0 auto;
              justify-self: end;
            }
        
            .rag-tab {
              flex: 0 0 auto;
              display: flex;
              flex-direction: row;
              align-items: center;
              gap: 6px;
        
              border: 1px solid GrayText;
              border-radius: 999px;
              padding: 3px 8px;
        
              background-color: ButtonFace;
              color: ButtonText;
        
              cursor: pointer;
              user-select: none;
            }
        
            .rag-tab.is-active {
              background-color: Highlight;
              color: HighlightText;
            }
        
            .rag-tab-title {
              display: block;
              color: inherit;
              overflow: hidden;
              text-overflow: ellipsis;
              white-space: nowrap;
              max-width: 130px;
            }
        
            .rag-tab-close {
              display: block;
              font-weight: bold;
              padding: 0 4px;
              cursor: pointer;
            }

            .rag-tab:hover {
              filter: brightness(0.95);
            }
            .rag-tab.is-active:hover {
              filter: brightness(1.10);
            }
        
            #rag-messages { 
              display: block;
              flex: 1;
              overflow: auto;
              overflow-x: hidden;
              padding: 8px;
              min-width: 0;
        
              background-color: Canvas;
              color: CanvasText;
        
              /* border: 1px solid GrayText;
              border-radius: 6px; */
            }
        
            .rag-msg-row {
              display: flex;
              flex-direction: row;
              margin: 6px 0;
              min-width: 0;
            }
            .rag-msg-row.is-user { justify-content: flex-end; }
            .rag-msg-row.is-assistant { justify-content: flex-start; }
        
            .rag-bubble {
              display: block;
              max-width: 85%;
              min-width: 0;
              overflow: hidden;
              border: 1px solid GrayText;
              border-radius: 10px;
              padding: 8px;
              white-space: normal;
        
              background-color: Canvas;
              color: CanvasText;
            }
        
            .rag-bubble.is-user {
              background-color: ButtonFace;
              color: ButtonText;
            }
        
            .rag-bubble-text {
              display: block;
              user-select: text;
              min-width: 0;
              max-width: 100%;
              overflow-wrap: anywhere;
              word-break: break-word;
            }
            .rag-bubble-text * {
              max-width: 100%;
              min-width: 0;
              overflow-wrap: anywhere;
              word-break: break-word;
            }

            .rag-bubble-text.is-plain {
              white-space: pre-wrap;
            }

            .rag-bubble-text p {
              margin: 0 0 0.5em 0;
            }
            .rag-bubble-text p:last-child {
              margin-bottom: 0;
            }
            .rag-bubble-text ul,
            .rag-bubble-text ol {
              margin: 0.25em 0 0.5em 1.25em;
              padding: 0;
            }
            .rag-bubble-text li {
              margin: 0.15em 0;
            }
            .rag-bubble-text h1,
            .rag-bubble-text h2,
            .rag-bubble-text h3,
            .rag-bubble-text h4,
            .rag-bubble-text h5,
            .rag-bubble-text h6 {
              margin: 0.2em 0 0.35em 0;
              font-size: 1em;
            }
            .rag-bubble-text blockquote {
              margin: 0.25em 0;
              padding-left: 0.6em;
              border-left: 2px solid GrayText;
              opacity: 0.9;
            }
            .rag-bubble-text code {
              font-family: monospace;
              background: color-mix(in srgb, CanvasText 8%, Canvas);
              padding: 0.05em 0.25em;
              border-radius: 4px;
              white-space: pre-wrap;
            }
            .rag-bubble-text .rag-code-block {
              margin: 0.25em 0;
              padding: 0.55em;
              border: 1px solid GrayText;
              border-radius: 6px;
              overflow-x: hidden;
              max-width: 100%;
              box-sizing: border-box;
              white-space: pre-wrap;
              background: color-mix(in srgb, CanvasText 6%, Canvas);
            }
            .rag-bubble-text .rag-code-block code {
              background: transparent;
              padding: 0;
              white-space: pre-wrap;
            }
            .rag-bubble-text a {
              text-decoration: underline;
            }
            .rag-bubble-text .rag-inline-source {
              cursor: pointer;
            }
        
            .rag-sources {
              display: block;
              margin-top: 8px;
              font-size: 0.9em;
              padding-top: 6px;
              border-top: 1px solid GrayText;
            }
        
            .rag-sources-header {
              display: block;
              font-weight: bold;
            }
        
            .rag-sources-list {
              display: block;
            }
        
            .rag-sources-line {
              display: block;
              white-space: pre-wrap;
              overflow-wrap: anywhere;
              word-break: break-word;
              cursor: pointer;
            }
            .rag-sources-line:hover {
              text-decoration: underline;
            }
        
            #rag-input-row {
              display: flex;
              flex-direction: row;
              gap: 6px;
              align-items: center;
              min-width: 0;
            }
        
            #rag-query-input {
              display: block;
              flex: 1;
              min-width: 0;
              width: 0;
              line-height: 28px;
              padding: 0 8px;
            }

            #rag-nav-top {
              display: flex;
              justify-content: center;
              margin-bottom: 6px;
            }

            #rag-query-input,
            #rag-query-button,
            #rag-new-chat,
            #rag-scroll-top,
            #rag-scroll-bottom {
              box-sizing: border-box;
              height: 28px;
              padding: 0 10px;
            }

            #rag-query-button,
            #rag-new-chat {
              display: flex;
              align-items: center;
              justify-content: center;
              padding: 0 12px;
              flex: 0 0 auto;
            }

            #rag-scroll-top,
            #rag-scroll-bottom {
              flex: 0 0 auto;
              width: 28px;
              padding: 0;
              font-size: 14px;
            }
            
            .rag-tab-title-edit {
              font: inherit;
              color: inherit;
              background: Canvas;
              box-sizing: border-box;
            
              max-width: 130px;
              width: 130px;
              padding: 0 6px;
            
              border: 1px solid GrayText;
              border-radius: 6px;
              height: 20px;
            }
          </html:style>
          <div id="rag-root">
            <div id="rag-nav-top">
              <html:button
                id="rag-scroll-bottom"
                title="Jump to latest message"
              >⬇</html:button>
            </div>
            <div id="rag-messages"></div>
        
            <div id="rag-input-row">
              <html:button id="rag-scroll-top" title="First message">⬆</html:button>
              <html:input id="rag-query-input" type="text" data-l10n-id="rag-query-input-placeholder"/>
              <html:button id="rag-query-button" data-l10n-id="rag-query-button-label">Ask</html:button>
            </div>

            <div id="rag-tabs-row">
              <div id="rag-tabs"></div>
              <html:button id="rag-new-chat">+</html:button>
            </div>
          </div>
      `,
      onRender: async ({ body /*, item*/ }) => {
        const doc = body.ownerDocument;
        const win = body.ownerDocument?.defaultView as Window | null;
        if (!doc || !win) return;

        const idbFactory = (win.indexedDB ?? win.mozIndexedDB) as
          | IDBFactory
          | undefined;
        if (!idbFactory) return;

        if (!this.chatDB) this.chatDB = new ChatDB(idbFactory);

        const tabsEl = body.querySelector("#rag-tabs") as HTMLElement;
        const newChatBtn = body.querySelector(
          "#rag-new-chat",
        ) as HTMLButtonElement;
        const messagesEl = body.querySelector("#rag-messages") as HTMLElement;
        const input = body.querySelector(
          "#rag-query-input",
        ) as HTMLInputElement;
        const sendBtn = body.querySelector(
          "#rag-query-button",
        ) as HTMLButtonElement;
        const scrollTopBtn = body.querySelector(
          "#rag-scroll-top",
        ) as HTMLButtonElement;
        const scrollBottomBtn = body.querySelector(
          "#rag-scroll-bottom",
        ) as HTMLButtonElement;

        if (
          !tabsEl ||
          !newChatBtn ||
          !messagesEl ||
          !input ||
          !sendBtn ||
          !scrollTopBtn ||
          !scrollBottomBtn
        )
          return;

        const showSourceOpenError = (error: unknown, sourceLabel: string) => {
          const details =
            error instanceof Error ? `\n\nDetails: ${error.message}` : "";
          const message =
            `Could not open source ${sourceLabel}.\n\n` +
            "Likely cause: this source belongs to a different Zotero account or library than the one currently open." +
            details;
          try {
            if (typeof Zotero.alert === "function") {
              Zotero.alert(win, "Source unavailable", message);
            } else {
              win.alert(message);
            }
          } catch (dialogError: any) {
            Zotero.logError?.(dialogError);
          }
        };

        let sessions: ChatSession[] = await this.chatDB.listSessions();
        let renamingSessionId: string | null = null;
        let currentSessionId: string | null = sessions[0]?.id ?? null;

        if (!currentSessionId) {
          const session = await this.chatDB.createSession(
            getString("chat-new-title"),
          );
          sessions = [session];
          currentSessionId = session.id;
        }

        const beginRenameSession = async (s: ChatSession, tab: HTMLElement) => {
          if (renamingSessionId) return;
          renamingSessionId = s.id;
          tab.dataset.editing = "1";

          const titleEl = tab.querySelector(
            ".rag-tab-title",
          ) as HTMLElement | null;
          if (!titleEl) {
            renamingSessionId = null;
            tab.dataset.editing = "0";
            return;
          }

          const oldTitle = (s.title ?? "").trim();

          const inputEl = ztoolkit.UI.createElement(
            body.ownerDocument!,
            "input",
          ) as HTMLInputElement;
          inputEl.classList.add("rag-tab-title-edit");
          inputEl.value = oldTitle;
          inputEl.placeholder = "Chat";

          inputEl.onclick = (e) => e.stopPropagation();
          inputEl.onmousedown = (e) => e.stopPropagation();

          const finish = async (apply: boolean) => {
            if (tab.dataset.editing !== "1") return;

            tab.dataset.editing = "0";
            renamingSessionId = null;

            const nextTitle = inputEl.value.trim();

            if (apply && nextTitle && nextTitle !== oldTitle) {
              await this.chatDB!.renameSession(s.id, nextTitle, true);
            }
            await renderTabs();
          };

          inputEl.onkeydown = (e) => {
            assert(e instanceof KeyboardEvent);
            e.stopPropagation();
            if (e.key === "Enter") {
              e.preventDefault();
              void finish(true);
            } else if (e.key === "Escape") {
              e.preventDefault();
              void finish(false);
            }
          };

          inputEl.onblur = () => void finish(true);

          tab.replaceChild(inputEl, titleEl);

          inputEl.focus();
          inputEl.select();
        };

        const renderTabs = async () => {
          sessions = await this.chatDB!.listSessions();
          if (!currentSessionId && sessions.length)
            currentSessionId = sessions[0].id;

          tabsEl.innerHTML = "";
          sessions.forEach((s) => {
            const tab = ztoolkit.UI.createElement(body.ownerDocument!, "div");
            tab.classList.add("rag-tab");
            if (s.id === currentSessionId) tab.classList.add("is-active");

            const title = ztoolkit.UI.createElement(
              body.ownerDocument!,
              "span",
            );
            title.classList.add("rag-tab-title");
            title.textContent = s.title || "Chat";
            title.ondblclick = (ev) => {
              ev.stopPropagation();
              void beginRenameSession(s, tab);
            };
            tab.title = s.title || "Chat";

            const close = ztoolkit.UI.createElement(
              body.ownerDocument!,
              "span",
            );
            close.classList.add("rag-tab-close");
            close.textContent = "×";
            close.title = "Close";

            close.onclick = async (ev) => {
              ev.stopPropagation();
              await this.chatDB!.deleteSession(s.id);

              const after = await this.chatDB!.listSessions();
              currentSessionId = after[0]?.id ?? null;
              if (!currentSessionId) {
                const ns = await this.chatDB!.createSession("New chat");
                currentSessionId = ns.id;
              }
              await renderTabs();
              await renderMessages();
            };

            tab.onclick = async (event) => {
              if ((event as MouseEvent).detail > 1) return;
              if (tab.dataset.editing === "1") return;
              currentSessionId = s.id;
              await renderTabs();
              await renderMessages();
              input.focus();
            };

            tab.appendChild(title);
            tab.appendChild(close);
            tabsEl.appendChild(tab);
          });
        };

        const renderMessages = async () => {
          if (!currentSessionId) return;

          const msgs = await this.chatDB!.listMessages(currentSessionId);
          messagesEl.innerHTML = "";
          messageSources.clear();

          msgs.forEach((m) => appendMessageNode(m));
          scrollToBottom();
        };

        const messageSources = new Map<string, Source[]>();

        const appendMessageNode = (m: ChatMessage) => {
          messageSources.set(m.id, m.sources ?? []);

          const row = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          row.dataset.msgId = m.id;
          row.classList.add("rag-msg-row");
          row.classList.add(m.role === "user" ? "is-user" : "is-assistant");

          const bubble = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          bubble.classList.add("rag-bubble");
          if (m.role === "user") bubble.classList.add("is-user");

          const text = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          text.classList.add("rag-bubble-text");
          if (m.role === "assistant") {
            text.innerHTML = renderAssistantMarkdown(m.content, m.sources ?? []);
          } else {
            text.classList.add("is-plain");
            text.textContent = m.content;
          }
          bubble.appendChild(text);

          if (m.role === "assistant" && m.sources && m.sources.length) {
            const sourcesWrap = ztoolkit.UI.createElement(
              body.ownerDocument!,
              "div",
            );
            sourcesWrap.classList.add("rag-sources");

            const header = ztoolkit.UI.createElement(
              body.ownerDocument!,
              "div",
            );
            header.classList.add("rag-sources-header");
            header.textContent = getString("sources-header");

            const list = ztoolkit.UI.createElement(body.ownerDocument!, "div");
            list.classList.add("rag-sources-list");

            for (const source of m.sources) {
              const line = ztoolkit.UI.createElement(
                body.ownerDocument!,
                "div",
              );
              line.classList.add("rag-sources-line");
              line.onclick = async () => {
                try {
                  await showZoteroSource(source.zotero_id, false);
                } catch (e: any) {
                  Zotero.logError?.(e);
                  showSourceOpenError(e, source.id);
                }
              };
              line.ondblclick = async () => {
                try {
                  await showZoteroSource(source.zotero_id, true);
                } catch (e: any) {
                  Zotero.logError?.(e);
                  showSourceOpenError(e, source.id);
                }
              };
              line.textContent = `${source.id}: ${source.filename}${formatSourcePages(source.pages)}`;
              list.appendChild(line);
            }

            sourcesWrap.appendChild(header);
            sourcesWrap.appendChild(list);
            bubble.appendChild(sourcesWrap);
          }

          row.appendChild(bubble);
          messagesEl.appendChild(row);
        };

        let autoScrollEnabled = true;

        const scrollToBottom = () => {
          if (!autoScrollEnabled) return;
          const side = doc.getElementById(
            "zotero-view-item",
          ) as HTMLElement | null;
          if (!side) throw new Error("No #zotero-view-item found");

          win.requestAnimationFrame(() => {
            win.requestAnimationFrame(() => {
              /* for some reason the scrollHeight will not reset when we remove chat elements.
                 so just updating it will recover from the illegal position */
              side.scrollTop = side.scrollHeight + 100;
            });
          });
        };

        messagesEl.addEventListener("wheel", () => {
          autoScrollEnabled = false;
        });
        messagesEl.addEventListener("touchmove", () => {
          autoScrollEnabled = false;
        });
        messagesEl.addEventListener("click", async (event) => {
          const target = event.target as HTMLElement | null;
          const sourceAnchor = target?.closest(
            ".rag-inline-source",
          ) as HTMLElement | null;
          if (!sourceAnchor) return;

          event.preventDefault();

          const sourceId = sourceAnchor.getAttribute("data-source-id");
          const row = sourceAnchor.closest("[data-msg-id]") as HTMLElement | null;
          const msgId = row?.dataset.msgId;
          if (!sourceId || !msgId) return;

          const source = (messageSources.get(msgId) ?? []).find(
            (s) => s.id === sourceId,
          );
          if (!source) return;
          try {
            await showZoteroSource(source.zotero_id, false);
          } catch (e: any) {
            Zotero.logError?.(e);
            showSourceOpenError(e, source.id);
          }
        });
        messagesEl.addEventListener("dblclick", async (event) => {
          const target = event.target as HTMLElement | null;
          const sourceAnchor = target?.closest(
            ".rag-inline-source",
          ) as HTMLElement | null;
          if (!sourceAnchor) return;

          event.preventDefault();

          const sourceId = sourceAnchor.getAttribute("data-source-id");
          const row = sourceAnchor.closest("[data-msg-id]") as HTMLElement | null;
          const msgId = row?.dataset.msgId;
          if (!sourceId || !msgId) return;

          const source = (messageSources.get(msgId) ?? []).find(
            (s) => s.id === sourceId,
          );
          if (!source) return;
          try {
            await showZoteroSource(source.zotero_id, true);
          } catch (e: any) {
            Zotero.logError?.(e);
            showSourceOpenError(e, source.id);
          }
        });

        const scrollToFirstMessage = () => {
          autoScrollEnabled = false;

          const side = doc.getElementById("zotero-view-item") as HTMLElement | null;
          if (!side) throw new Error("No #zotero-view-item found");

          const navTop = body.querySelector("#rag-nav-top") as HTMLElement | null;
          if (!navTop) return;

          // Position of navTop relative to the scroll container
          const sideRect = side.getBoundingClientRect();
          const navRect = navTop.getBoundingClientRect();

          // Current scrollTop + delta between nav and container top
          const targetTop = side.scrollTop + (navRect.top - sideRect.top);

          side.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
        };

        const scrollToLastMessage = () => {
          autoScrollEnabled = true;
          scrollToBottom();
        };

        const setMessageText = (
          msgId: string,
          value: string,
          sources?: Source[],
        ) => {
          if (sources) {
            messageSources.set(msgId, sources);
          }
          const effectiveSources = messageSources.get(msgId) ?? [];

          const row = messagesEl.querySelector(
            `[data-msg-id="${msgId}"]`,
          ) as HTMLElement | null;
          const textEl = row?.querySelector(
            ".rag-bubble-text",
          ) as HTMLElement | null;
          if (textEl) {
            if (row?.classList.contains("is-assistant")) {
              textEl.innerHTML = renderAssistantMarkdown(
                value,
                effectiveSources,
              );
            } else {
              textEl.classList.add("is-plain");
              textEl.textContent = value;
            }
          }
        };

        const ensureSession = async (): Promise<string> => {
          if (currentSessionId) return currentSessionId;
          const s = await this.chatDB!.createSession("New chat");
          currentSessionId = s.id;
          await renderTabs();
          return currentSessionId!;
        };

        const maybeRefreshAutoTitle = async (sessionId: string) => {
          try {
            const session = await this.chatDB!.getSession(sessionId);
            if (!session || session.isTitleUserSet) return;

            const messages = await this.chatDB!.listMessages(sessionId);
            const titleMessages: ChatTitleMessage[] = messages
              .filter((m) => (m.content ?? "").trim().length > 0)
              .map((m) => ({
                role: m.role,
                content: m.content,
              }));
            if (!titleMessages.length) return;

            const suggestedTitle =
              await this.ragClient.generateChatTitle(titleMessages);
            if (!suggestedTitle) return;

            const latestSession = await this.chatDB!.getSession(sessionId);
            if (!latestSession || latestSession.isTitleUserSet) return;

            await this.chatDB!.renameSession(sessionId, suggestedTitle, false);
            await renderTabs();
          } catch (e) {
            const err =
              e instanceof Error
                ? e
                : new Error(typeof e === "string" ? e : JSON.stringify(e));
            Zotero.logError?.(err);
          }
        };

        const createAbortController = (): AbortController | null => {
          const scopedWin = body.ownerDocument?.defaultView;
          if (!scopedWin?.AbortController) return null;
          return new scopedWin.AbortController();
        };

        let activeQueryAbortController: AbortController | null = null;
        const askLabel = getString("query-button-label");
        const stopLabel = getString("stop-button-label");
        const stoppedMessage = getString("stopped-message");
        let isQueryRunning = false;

        const collectAppendOnlySources = (messages: ChatMessage[]): Source[] => {
          const out: Source[] = [];
          const seen = new Map<string, Source>();
          for (const message of messages) {
            for (const source of message.sources ?? []) {
              const key = `${source.zotero_id}\0${source.filename}`;
              const existing = seen.get(key);
              if (existing) {
                const merged = [...(existing.pages ?? []), ...(source.pages ?? [])];
                existing.pages = [...new Set(merged)].sort((a, b) => a - b);
                continue;
              }
              const next: Source = {
                id: `S${out.length + 1}`,
                filename: source.filename,
                zotero_id: source.zotero_id,
                pages: source.pages,
              };
              seen.set(key, next);
              out.push(next);
            }
          }
          return out;
        };

        const sendPrompt = async () => {
          if (isQueryRunning) {
            if (
              activeQueryAbortController &&
              !activeQueryAbortController.signal.aborted
            ) {
              activeQueryAbortController.abort();
            }
            return;
          }

          const prompt = input.value.trim();
          if (!prompt) return;

          const sessionId = await ensureSession();

          input.value = "";
          const controller = createAbortController();
          activeQueryAbortController = controller;
          isQueryRunning = true;
          sendBtn.textContent = stopLabel;
          sendBtn.disabled = !controller;

          const historyMessages = await this.chatDB!.listMessages(sessionId);

          const modelMessages: ChatTitleMessage[] = historyMessages
            .filter((m) => (m.content ?? "").trim().length > 0)
            .map((m) => ({
              role: m.role,
              content: m.content,
            }));
          const appendOnlySources = collectAppendOnlySources(historyMessages);
          const userMsg = await this.chatDB!.addMessage({
            sessionId,
            role: "user",
            content: prompt,
          });
          appendMessageNode(userMsg);
          scrollToBottom();

          const pending = await this.chatDB!.addMessage({
            sessionId,
            role: "assistant",
            content: getString("querying-message"),
          });
          appendMessageNode(pending);
          scrollToBottom();

          let answer = "";
          let sawFirstToken = false;
          try {
            let sources: Source[] = [];

            setMessageText(pending.id, getString("querying-message"));

            for await (const msg of this.ragClient.query(
              prompt,
              modelMessages,
              appendOnlySources,
              controller?.signal,
            )) {
              if (msg.type === "updateProgress") {
                if (!sawFirstToken) {
                  setMessageText(
                    pending.id,
                    `${getString("querying-message")} (${msg.stage})`,
                  );
                }
                if (msg.debug !== undefined) {
                  Zotero.debug("[RAG] " + msg.debug);
                }
              }

              if (msg.type === "setSources") {
                sources = msg.sources;
                setMessageText(pending.id, answer, sources);
              }

              if (msg.type === "token") {
                if (!sawFirstToken) {
                  sawFirstToken = true;
                  answer = "";
                }
                answer += msg.token;
                setMessageText(pending.id, answer, sources);
                scrollToBottom();
              }

              if (msg.type === "done") {
                break;
              }
            }

            await this.chatDB!.updateMessage(pending.id, {
              content: answer,
              sources,
            });

            await renderMessages();
            void maybeRefreshAutoTitle(sessionId);
          } catch (e: any) {
            const isAbortError =
              !!e &&
              typeof e === "object" &&
              "name" in e &&
              (e as { name?: string }).name === "AbortError";
            if (isAbortError) {
              const trimmedAnswer = answer.trim();
              await this.chatDB!.updateMessage(pending.id, {
                content:
                  sawFirstToken && trimmedAnswer ? trimmedAnswer : stoppedMessage,
              });
            } else {
              await this.chatDB!.updateMessage(pending.id, {
                content: getString("error-prefix", {
                  args: { message: e?.message ?? String(e) },
                }),
              });
            }
            await renderMessages();
          } finally {
            if (activeQueryAbortController === controller) {
              activeQueryAbortController = null;
            }
            isQueryRunning = false;
            sendBtn.textContent = askLabel;
            sendBtn.disabled = false;
            input.focus();
          }
        };

        newChatBtn.onclick = async () => {
          const s = await this.chatDB!.createSession("New chat");
          currentSessionId = s.id;
          await renderTabs();
          await renderMessages();
          input.focus();
        };

        sendBtn.onclick = sendPrompt;
        input.onkeydown = (e) => {
          const ke = e as KeyboardEvent;
          if (ke.key === "Enter") {
            e.preventDefault();
            void sendPrompt();
          }
        };

        scrollTopBtn.onclick = scrollToFirstMessage;
        scrollBottomBtn.onclick = scrollToLastMessage;

        await renderTabs();
        await renderMessages();
      },
    });
  }
}
