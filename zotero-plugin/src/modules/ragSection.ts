import { RagClient } from "./ragClient";
import { getString } from "../utils/locale";
import { ChatDB, ChatMessage, ChatSession } from "./ragStorage";

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
          <div id="rag-root"
               style="padding:10px; display:flex; flex-direction:column; gap:8px; height:100%;
                      background-color: Canvas; color: CanvasText;">
            <div id="rag-tabs-row" style="display:flex; flex-direction:row; gap:6px; align-items:center;">
              <div id="rag-tabs"
                   style="display:flex; flex-direction:row; gap:6px; overflow-x:auto; white-space:nowrap; flex:1;"></div>
              <html:button id="rag-new-chat" style="display:block;">+</html:button>
            </div>

            <div id="rag-messages"
                 style="display:block; flex:1; overflow:auto; padding:8px;
                        background-color: Canvas; color: CanvasText;">
            </div>

            <div id="rag-input-row" style="display:flex; flex-direction:row; gap:6px; align-items:flex-end;">
              <html:input id="rag-query-input" type="text" style="display:block; flex:1;" data-l10n-id="rag-query-input-placeholder"/>
              <html:button id="rag-query-button" style="display:block;" data-l10n-id="rag-query-button-label">Ask</html:button>
            </div>
          </div>
      `,
      onRender: async ({ body /*, item*/ }) => {
        const win = body.ownerDocument?.defaultView as Window | null;
        if (!win) return;

        const idbFactory = (win.indexedDB ?? (win as any).mozIndexedDB) as IDBFactory | undefined;
        if (!idbFactory) return;

        if (!this.chatDB) this.chatDB = new ChatDB(idbFactory);

        const tabsEl = body.querySelector("#rag-tabs") as HTMLElement;
        const newChatBtn = body.querySelector("#rag-new-chat") as HTMLButtonElement;
        const messagesEl = body.querySelector("#rag-messages") as HTMLElement;
        const input = body.querySelector("#rag-query-input") as HTMLInputElement;
        const sendBtn = body.querySelector("#rag-query-button") as HTMLButtonElement;

        if (!tabsEl || !newChatBtn || !messagesEl || !input || !sendBtn) return;

        let sessions: ChatSession[] = await this.chatDB.listSessions();
        let currentSessionId: string | null = sessions[0]?.id ?? null;

        if (!currentSessionId) {
          const s = await this.chatDB.createSession(getString("rag-chat-new-title") ?? "New chat");
          sessions = [s];
          currentSessionId = s.id;
        }

        const renderTabs = async () => {
          sessions = await this.chatDB.listSessions();
          if (!currentSessionId && sessions.length) currentSessionId = sessions[0].id;

          tabsEl.innerHTML = "";
          sessions.forEach((s) => {
            const tab = ztoolkit.UI.createElement(body.ownerDocument!, "div");
            tab.style.display = "flex";
            tab.style.flexDirection = "row";
            tab.style.alignItems = "center";
            tab.style.gap = "6px";
            tab.style.border = "1px solid GrayText";
            tab.style.borderRadius = "999px";
            tab.style.padding = "3px 8px";

            if (s.id === currentSessionId) {
              tab.style.backgroundColor = "Highlight";
              tab.style.color = "HighlightText";
            } else {
              tab.style.backgroundColor = "ButtonFace";
              tab.style.color = "ButtonText";
            }

            const title = ztoolkit.UI.createElement(body.ownerDocument!, "span");
            title.style.display = "block";
            title.style.color = "inherit";
            title.textContent = s.title || "Chat";

            const close = ztoolkit.UI.createElement(body.ownerDocument!, "span");
            close.style.display = "block";
            close.textContent = "×";
            close.style.fontWeight = "bold";
            close.style.padding = "0 4px";
            close.style.cursor = "pointer";
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

            tab.onclick = async () => {
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
          row.style.display = "flex";
          row.style.flexDirection = "row";
          row.style.justifyContent = m.role === "user" ? "flex-end" : "flex-start";
          row.style.margin = "6px 0";

          const bubble = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          bubble.style.display = "block";
          bubble.style.maxWidth = "85%";
          bubble.style.border = "1px solid GrayText";
          bubble.style.borderRadius = "10px";
          bubble.style.padding = "8px";
          bubble.style.whiteSpace = "pre-wrap";
          if (m.role === "user") {
            bubble.style.backgroundColor = "ButtonFace";
             bubble.style.color = "ButtonText";
          } else {
            bubble.style.backgroundColor = "Canvas";
            bubble.style.color = "CanvasText";
          }

          const text = ztoolkit.UI.createElement(body.ownerDocument!, "div");
          text.style.display = "block";
          text.style.whiteSpace = "pre-wrap";
          text.textContent = m.content;

          bubble.appendChild(text);

          if (m.role === "assistant" && m.sources && Object.keys(m.sources).length) {
            const sourcesWrap = ztoolkit.UI.createElement(body.ownerDocument!, "div");
            sourcesWrap.style.display = "block";
            sourcesWrap.style.marginTop = "8px";
            sourcesWrap.style.fontSize = "0.9em";
            sourcesWrap.style.paddingTop = "6px";
            sourcesWrap.style.borderTop = "1px solid GrayText";

            const header = ztoolkit.UI.createElement(body.ownerDocument!, "div");
            header.style.display = "block";
            header.style.fontWeight = "bold";
            header.textContent = getString("rag-sources-header") ?? "Sources:";

            const list = ztoolkit.UI.createElement(body.ownerDocument!, "div");
            list.style.display = "block";

            for (const k of Object.keys(m.sources)) {
              const line = ztoolkit.UI.createElement(body.ownerDocument!, "div");
              line.style.display = "block";
              line.style.whiteSpace = "pre-wrap";
              line.textContent = `${k}: ${m.sources[k]}`;
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
          messagesEl.scrollTop = messagesEl.scrollHeight;
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
            content: getString("querying-message") ?? "Thinking…",
          });
          appendMessageNode(pending);
          scrollToBottom();

          try {
            const result = await this.ragClient.query(prompt);

            await this.chatDB!.updateMessage(pending.id, {
              content: result.response,
              sources: result.sources,
            });

            await renderTabs();
            await renderMessages();
          } catch (e: any) {
            await this.chatDB!.updateMessage(pending.id, {
              content: (getString("error-prefix", { args: { message: e?.message ?? String(e) } })
                  ?? `Error: ${e?.message ?? String(e)}`),
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
