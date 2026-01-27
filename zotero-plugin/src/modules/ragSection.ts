import {RagClient} from "./ragClient";
import {getString} from "../utils/locale";

export class RagSection {
  private static ragClient = new RagClient();

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
        <div id="rag-section-container" style="padding: 10px; display: flex; flex-direction: column; gap: 10px;">
          <div style="display: flex; gap: 5px;">
            <html:input id="rag-query-input" type="text" style="flex: 1;" data-l10n-id="rag-query-input-placeholder"/>
            <html:button id="rag-query-button" data-l10n-id="rag-query-button-label">Ask</html:button>
          </div>
          <div id="rag-response-container" style="border: 1px solid #ccc; padding: 5px; min-height: 50px; white-space: pre-wrap" data-l10n-id="rag-response-placeholder">
            Response will appear here...
          </div>
          <div id="rag-sources-container" style="display: none; flex-direction: column; gap: 5px;">
            <div style="font-weight: bold;" data-l10n-id="rag-sources-header">Sources:</div>
            <div id="rag-sources-list" style="font-size: 0.9em;display: block"></div>
          </div>
        </div>
      `,
      onRender: ({ body, item }) => {
        const input = body.querySelector("#rag-query-input") as HTMLInputElement;
        const button = body.querySelector("#rag-query-button") as HTMLButtonElement;
        const responseContainer = body.querySelector("#rag-response-container") as HTMLElement;
        const sourcesContainer = body.querySelector("#rag-sources-container") as HTMLElement;
        const sourcesList = body.querySelector("#rag-sources-list") as HTMLElement;

        if (!button || !input || !responseContainer || !sourcesContainer || !sourcesList || !item) return;

        button.onclick = async () => {
          const prompt = input.value.trim();
          if (!prompt) return;

          button.disabled = true;
          responseContainer.textContent = getString("querying-message");
          sourcesContainer.style.display = "none";
          sourcesList.innerHTML = "";

          try {
            const result = await this.ragClient.query(prompt);
            responseContainer.textContent = result.response;

            const sourceKeys = Object.keys(result.sources);
            if (sourceKeys.length > 0) {
              sourcesContainer.style.display = "flex";
              sourceKeys.forEach((key) => {
                const sourceItem = ztoolkit.UI.createElement(body.ownerDocument!!, "div");
                sourceItem.style.display = "block";
                sourceItem.style.whiteSpace = "pre-wrap";
                sourceItem.textContent = `${key}: ${result.sources[key]}`;
                sourcesList.appendChild(sourceItem);
              });
            }
          } catch (e) {
            responseContainer.textContent = getString("error-prefix", {
              args: { message: e.message },
            });
          } finally {
            button.disabled = false;
          }
        };
        input.onkeydown = (e) => {
          if (e.key === "Enter") {
            button.click();
          }
        };
      },
    });
  }
}
