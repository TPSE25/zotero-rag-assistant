import randomString = Zotero.randomString;
import {RagConfig} from "./ragClient";

type RagHighlightRule = {
    id: string;
    enabled: boolean;
    colorHex: string;
    termsRaw: string;
};

export type RagPopupConfig = {
    rules: RagHighlightRule[];
};

function newRuleId() {
    return `rule_${randomString(10)}`;
}

let popupCfg: RagPopupConfig = { rules: [] };

function getPrefKey(): string {
    const addonRef = addon?.data?.config?.addonRef as string | undefined;
    const addonID = addon?.data?.config?.addonID as string | undefined;

    const ns = addonRef
        ? `extensions.zotero.${addonRef}.`
        : `extensions.zotero.${(addonID ?? "rag_highlight").replace(/[^a-zA-Z0-9_.-]/g, "_")}.`;

    return `${ns}highlightPopupConfig`;
}

function isPopupVisible(popup: HTMLElement): boolean {
    const win = popup.ownerDocument.defaultView;
    if (!win) return popup.style.display !== "none";
    return win.getComputedStyle(popup).display !== "none";
}

function loadCfgFromPrefs(): RagPopupConfig {
    try {
        const raw = Zotero.Prefs.get(getPrefKey(), true) as string | undefined;
        return raw ? JSON.parse(raw) : { rules: [{ id: newRuleId(), enabled: true, colorHex: "#ffeb3b", termsRaw: "" }] };
    } catch (e) {
        Zotero.debug?.(`RAG: failed to load prefs: ${String(e)}`);
        return { rules: [] };
    }
}

function saveCfgToPrefs(cfg: RagPopupConfig) {
    try {
        Zotero.Prefs.set(getPrefKey(), JSON.stringify(cfg), true);
    } catch (e) {
        Zotero.debug?.(`RAG: failed to save prefs: ${String(e)}`);
    }
}

function safeAppend(doc: Document, el: HTMLElement) {
    (doc.body || doc.head || doc.documentElement)?.appendChild(el);
}

function ensureRagStyles(doc: Document) {
    if (doc.getElementById("rag-highlight-style")) return;

    const style = doc.createElement("style");
    style.id = "rag-highlight-style";
    style.textContent = `
      .rag-popup {
        position: fixed;
        z-index: 999999;
        width: 360px;   
        max-width: 92vw;
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.2);
        box-shadow: 0 12px 34px rgba(0,0,0,0.25);
        background: var(--zotero-pane-bg, #fff);
        color: var(--zotero-text-color, #111);
        font-size: 13px;
        padding: 10px;
        display: none;
      }

      .rag-popup__header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
      }

      .rag-popup__title { font-weight: 600; }

      .rag-popup__close {
        border: none;
        background: transparent;
        color: inherit;
        font-size: 18px;
        line-height: 1;
        cursor: pointer;
        padding: 2px 6px;
        border-radius: 8px;
      }
      .rag-popup__close:hover { background: rgba(0,0,0,0.08); }

      .rag-checkbox {
        display: flex;
        align-items: center;
        gap: 8px;
        user-select: none;
        margin: 6px 0 10px;
      }

      .rag-section-title { font-weight: 600; margin: 12px 0 6px; }
      .rag-help { opacity: 0.8; margin-bottom: 8px; }

      .rag-rules { display: flex; flex-direction: column; gap: 8px; }

      .rag-rule {
        display: grid;
        grid-template-columns: 24px 42px 1fr 34px;
        gap: 8px;
        align-items: center;
        padding: 8px;
        border-radius: 12px;
        border: 1px solid rgba(0,0,0,0.18);
        background: rgba(0,0,0,0.02);
      }

      .rag-rule textarea {
        border: 1px solid rgba(0,0,0,0.22);
        border-radius: 10px;
        background: transparent;
        color: inherit;
        padding: 7px 8px;
        outline: none;
        width: 100%;
      }
      .rag-rule textarea:focus { border-color: rgba(0,0,0,0.38); }

      .rag-rule .rag-color {
        width: 42px;
        height: 34px;
        padding: 0;
        border: none;
        background: transparent;
        cursor: pointer;
      }

      .rag-icon-btn {
        width: 34px;
        height: 34px;
        border-radius: 10px;
        border: 1px solid rgba(0,0,0,0.22);
        background: transparent;
        color: inherit;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }
      .rag-icon-btn:hover { background: rgba(0,0,0,0.08); }

      .rag-actions {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        margin-top: 12px;
      }

      .rag-btn {
        padding: 6px 10px;
        border-radius: 10px;
        border: 1px solid rgba(0,0,0,0.25);
        background: transparent;
        color: inherit;
        cursor: pointer;
      }
      .rag-btn:hover { background: rgba(0,0,0,0.08); }
      .rag-btn--primary { background: rgba(0,0,0,0.08); }
    `;
    safeAppend(doc, style);
}

function renderRules(popup: HTMLDivElement) {
    const rulesHost = popup.querySelector<HTMLDivElement>("#rag-rules")!;
    rulesHost.innerHTML = "";

    for (const rule of popupCfg.rules) {
        const row = popup.ownerDocument.createElement("div");
        row.className = "rag-rule";
        row.dataset.ruleId = rule.id;

        row.innerHTML = `
          <input type="checkbox" class="rag-rule-enabled" title="Enable rule" />
          <input type="color" class="rag-color rag-rule-color" title="Rule color" />
          <textarea class="rag-rule-terms" placeholder="what to highlight"></textarea>
          <button type="button" class="rag-icon-btn" data-action="remove-rule" title="Remove rule">×</button>
        `;

        (row.querySelector<HTMLInputElement>(".rag-rule-enabled")!).checked = rule.enabled;
        (row.querySelector<HTMLInputElement>(".rag-rule-color")!).value = rule.colorHex;
        (row.querySelector<HTMLTextAreaElement>(".rag-rule-terms")!).value = rule.termsRaw;

        rulesHost.appendChild(row);
    }
}

function readUiIntoConfig(popup: HTMLDivElement) {
    const ruleEls = Array.from(popup.querySelectorAll<HTMLElement>("#rag-rules [data-rule-id]"));
    const rules: RagHighlightRule[] = ruleEls.map((el) => {
        const id = el.dataset.ruleId!;
        return {
            id,
            enabled: (el.querySelector<HTMLInputElement>(".rag-rule-enabled")!).checked,
            colorHex: (el.querySelector<HTMLInputElement>(".rag-rule-color")!).value,
            termsRaw: (el.querySelector<HTMLTextAreaElement >(".rag-rule-terms")!).value,
        };
    });

    popupCfg = { rules };
}

function ensurePopup(doc: Document, reader: any): HTMLDivElement {
    const existing = doc.getElementById("rag-highlight-popup");
    if (existing) return existing as HTMLDivElement;

    const popup = doc.createElement("div");
    popup.id = "rag-highlight-popup";
    popup.className = "rag-popup";

    popup.innerHTML = `
      <div class="rag-popup__header">
        <div class="rag-popup__title">Highlighting</div>
        <button type="button" class="rag-popup__close" id="rag-popup-close" aria-label="Close">×</button>
      </div>

      <div id="rag-rules" class="rag-rules"></div>

      <div class="rag-actions">
        <button type="button" class="rag-btn" id="rag-add-rule">+ Add rule</button>

        <div style="display:flex; gap:8px;">
          <button type="button" class="rag-btn" id="rag-save">Save</button>
          <button type="button" class="rag-btn rag-btn--primary" id="rag-execute">Execute</button>
        </div>
      </div>
    `;

    safeAppend(doc, popup);

    const close = () => (popup.style.display = "none");

    popup.querySelector<HTMLButtonElement>("#rag-popup-close")!.addEventListener("click", close);

    if (!popup.dataset.ragDocBound) {
        popup.dataset.ragDocBound = "1";

        doc.addEventListener("keydown", (e) => {
            if (e.key === "Escape") close();
        });

        doc.addEventListener("mousedown", (e) => {
            if (isPopupVisible(popup) && !popup.contains(e.target as Node)) close();
        });
    }

    popup.addEventListener("click", (e) => {
        const target = e.target as HTMLElement;
        const removeBtn = target.closest<HTMLButtonElement>("[data-action='remove-rule']");
        if (!removeBtn) return;

        const ruleEl = removeBtn.closest<HTMLElement>("[data-rule-id]");
        const ruleId = ruleEl?.dataset.ruleId;
        if (!ruleId) return;

        popupCfg.rules = popupCfg.rules.filter((r) => r.id !== ruleId);
        renderRules(popup);
    });

    popup.querySelector<HTMLButtonElement>("#rag-add-rule")!.addEventListener("click", () => {
        popupCfg.rules.push({
            id: newRuleId(),
            enabled: true,
            colorHex: "#90caf9",
            termsRaw: "",
        });
        renderRules(popup);
    });

    popup.querySelector("#rag-save")!.addEventListener("click", () => {
        readUiIntoConfig(popup);
        saveCfgToPrefs(popupCfg);
        close();
    });
    popup.querySelector("#rag-execute")!.addEventListener("click", async () => {
        const executeBtn = popup.querySelector<HTMLButtonElement>("#rag-execute")!;
        const oldLabel = executeBtn.textContent ?? "Execute";

        try {
            executeBtn.disabled = true;
            executeBtn.textContent = "Working…";

            readUiIntoConfig(popup);
            saveCfgToPrefs(popupCfg);

            const { RagClient } = await import("./ragClient");
            const { readCurrentPdf, createHighlightsFromAnalyzeResponse } = await import("./ragZoteroAnnotations");
            const pdfBlob = await readCurrentPdf(reader);
            const client = new RagClient();
            const request: RagConfig = {
                rules: popupCfg.rules
                    .filter((r) => r.enabled)
                    .map((r) => ({ id: r.id, termsRaw: r.termsRaw }))
            };
            const resp = await client.analyzePdf(pdfBlob, request);
            const created = await createHighlightsFromAnalyzeResponse(reader, popupCfg, resp);
            reader._iframeWindow?.console?.log?.(`RAG: created ${created} annotations`);
        } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            Zotero.debug?.(`RAG execute failed: ${msg}`);
            reader._iframeWindow?.alert?.(`RAG failed: ${msg}`);
        } finally {
            executeBtn.disabled = false;
            executeBtn.textContent = oldLabel;
        }
    });

    return popup;
}

function openPopupNearButton(popup: HTMLDivElement, btn: HTMLElement) {
    popup.style.display = "block";

    const rect = btn.getBoundingClientRect();
    const margin = 8;

    const win = popup.ownerDocument.defaultView!;
    const maxX = win.innerWidth - popup.offsetWidth - margin;
    const maxY = win.innerHeight - popup.offsetHeight - margin;

    popup.style.left = `${Math.max(margin, Math.min(rect.left, maxX))}px`;
    popup.style.top = `${Math.max(margin, Math.min(rect.bottom + margin, maxY))}px`;
}

let toolbarHandler: Parameters<typeof Zotero.Reader.registerEventListener>[1] | undefined;

export function registerReaderToolbarButton() {
    if (toolbarHandler) return;

    toolbarHandler = (event) => {
        const { reader, doc, append } = event;

        if ((reader as any).type && (reader as any).type !== "pdf") return;
        if (doc.getElementById("rag-highlight-button")) return;

        ensureRagStyles(doc);

        const btn = doc.createElement("button");
        btn.id = "rag-highlight-button";
        btn.classList.add("toolbar-button");
        btn.title = "Highlighting";

        const svgNS = "http://www.w3.org/2000/svg";
        const svg = doc.createElementNS(svgNS, "svg");
        svg.setAttribute("width", "20");
        svg.setAttribute("height", "20");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("fill", "none");
        svg.setAttribute("stroke", "currentColor");
        svg.setAttribute("stroke-width", "2");
        svg.setAttribute("stroke-linecap", "round");
        svg.setAttribute("stroke-linejoin", "round");

        const paths = [
            "M9 11l-5 5V19h3l5-5",
            "M9 11l7-7 4 4-7 7",
            "M15 5l4 4",
            "M19 15h3",
            "M19 19h3",
        ];

        for (const d of paths) {
            const path = doc.createElementNS(svgNS, "path");
            path.setAttribute("d", d);
            svg.appendChild(path);
        }

        svg.style.display = "block";
        svg.style.margin = "auto";
        btn.appendChild(svg);

        btn.addEventListener("click", () => {
            popupCfg = loadCfgFromPrefs();
            const popup = ensurePopup(doc, reader);

            if (isPopupVisible(popup)) {
                popup.style.display = "none";
                return;
            }
            renderRules(popup);
            openPopupNearButton(popup, btn);
        });

        append(btn);
    };

    Zotero.Reader.registerEventListener("renderToolbar", toolbarHandler, addon.data.config.addonID);
}

export function unregisterReaderToolbarButton() {
    if (!toolbarHandler) return;
    Zotero.Reader.unregisterEventListener("renderToolbar", toolbarHandler);
    toolbarHandler = undefined;
}
