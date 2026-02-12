import { RagClient } from "./ragClient";
import { getString } from "../utils/locale";
import { ChatDB, ChatMessage, ChatSession } from "./ragStorage";
import { showZoteroSource } from "./openSource";
import { assert } from "../utils/assert";

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
              padding: 8px;
        
              background-color: Canvas;
              color: CanvasText;
        
              /* border: 1px solid GrayText;
              border-radius: 6px; */
            }
        
            .rag-msg-row {
              display: flex;
              flex-direction: row;
              margin: 6px 0;
            }
            .rag-msg-row.is-user { justify-content: flex-end; }
            .rag-msg-row.is-assistant { justify-content: flex-start; }
        
            .rag-bubble {
              display: block;
              max-width: 85%;
              border: 1px solid GrayText;
              border-radius: 10px;
              padding: 8px;
              white-space: pre-wrap;
        
              background-color: Canvas;
              color: CanvasText;
            }
        
            .rag-bubble.is-user {
              background-color: ButtonFace;
              color: ButtonText;
            }
        
            .rag-bubble-text {
              display: block;
              white-space: pre-wrap;
              user-select: text;
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
            }
        
            #rag-query-input {
              display: block;
              flex: 1;
              line-height: 28px;
              padding: 0 8px;
            }

            #rag-query-input,
            #rag-query-button,
            #rag-new-chat {
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
            <div id="rag-messages"></div>
        
            <div id="rag-input-row">
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

        if (!tabsEl || !newChatBtn || !messagesEl || !input || !sendBtn) return;

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
              await this.chatDB!.renameSession(s.id, nextTitle);
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

          msgs.forEach((m) => appendMessageNode(m));
          scrollToBottom();
        };

        const appendMessageNode = (m: ChatMessage) => {
          const row = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          row.dataset.msgId = m.id;
          row.classList.add("rag-msg-row");
          row.classList.add(m.role === "user" ? "is-user" : "is-assistant");

          const bubble = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          bubble.classList.add("rag-bubble");
          if (m.role === "user") bubble.classList.add("is-user");

          const text = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          text.classList.add("rag-bubble-text");
          text.textContent = m.content;
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
                }
              };
              line.ondblclick = async () => {
                try {
                  await showZoteroSource(source.zotero_id, true);
                } catch (e: any) {
                  Zotero.logError?.(e);
                }
              };
              line.textContent = `${source.id}: ${source.filename}`;
              list.appendChild(line);
            }

            sourcesWrap.appendChild(header);
            sourcesWrap.appendChild(list);
            bubble.appendChild(sourcesWrap);
          }

          row.appendChild(bubble);
          messagesEl.appendChild(row);
        };

        const scrollToBottom = () => {
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

        const setMessageText = (msgId: string, value: string) => {
          const row = messagesEl.querySelector(
            `[data-msg-id="${msgId}"]`,
          ) as HTMLElement | null;
          const textEl = row?.querySelector(
            ".rag-bubble-text",
          ) as HTMLElement | null;
          if (textEl) textEl.textContent = value;
        };

        const ensureSession = async (): Promise<string> => {
          if (currentSessionId) return currentSessionId;
          const s = await this.chatDB!.createSession("New chat");
          currentSessionId = s.id;
          await renderTabs();
          return currentSessionId!;
        };

        const sendPrompt = async () => {
          const prompt = input.value.trim();
          if (!prompt) return;

          const sessionId = await ensureSession();

          const session = await this.chatDB!.getSession(sessionId);
          if (session && (session.title === "New chat" || !session.title)) {
            const t = prompt.length > 32 ? `${prompt.slice(0, 32)}…` : prompt;
            await this.chatDB!.renameSession(sessionId, t);
          }

          input.value = "";
          sendBtn.disabled = true;

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

          try {
            let answer = "";
            let sources: any[] = [];
            let sawFirstToken = false;

            setMessageText(pending.id, getString("querying-message"));

            for await (const msg of this.ragClient.query(prompt)) {
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
              }

              if (msg.type === "token") {
                if (!sawFirstToken) {
                  sawFirstToken = true;
                  answer = "";
                }
                answer += msg.token;
                setMessageText(pending.id, answer);
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

            await renderTabs();
            await renderMessages();
          } catch (e: any) {
            await this.chatDB!.updateMessage(pending.id, {
              content: getString("error-prefix", {
                args: { message: e?.message ?? String(e) },
              }),
            });
            await renderMessages();
          } finally {
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
          assert(e instanceof KeyboardEvent);
          if (e.key === "Enter") {
            e.preventDefault();
            void sendPrompt();
          }
        };

        await renderTabs();
        await renderMessages();
      },
    });
  }
}
