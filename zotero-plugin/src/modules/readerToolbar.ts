import randomString = Zotero.randomString;
import { RagConfig } from "./ragClient";
import { getString } from "../utils/locale";

type RagHighlightRule = {
  id: string;
  enabled: boolean;
  colorHex: string;
  termsRaw: string;
};

export type RagPopupConfig = {
  rules: RagHighlightRule[];
  pageRange: string;
};

function newRuleId() {
  return `rule_${randomString(10)}`;
}

let popupCfg: RagPopupConfig = { rules: [], pageRange: "" };
let activeExecuteAbortController: AbortController | null = null;

function createAbortControllerFromDoc(doc: Document): AbortController | null {
  const win = doc.defaultView
  if (!win?.AbortController) return null;
  return new win.AbortController();
}

function getPrefKey(): string {
  const addonRef = addon?.data?.config?.addonRef as string | undefined;
  const addonID = addon?.data?.config?.addonID as string | undefined;

  const ns = addonRef
    ? `extensions.zotero.${addonRef}.`
    : `extensions.zotero.${(addonID ?? "rag_highlight").replace(/[^a-zA-Z0-9_.-]/g, "_")}.`;

  return `${ns}highlightPopupConfig`;
}

function isPopupVisible(popup: HTMLElement): boolean {
  const win = popup.ownerDocument!.defaultView;
  if (!win) return popup.style.display !== "none";
  return win.getComputedStyle(popup)!.display !== "none";
}

function loadCfgFromPrefs(): RagPopupConfig {
  try {
    const raw = Zotero.Prefs.get(getPrefKey(), true) as string | undefined;
    if (!raw) {
      return {
          rules: [
            {
              id: newRuleId(),
              enabled: true,
              colorHex: "#ffeb3b",
              termsRaw: "",
            },
          ],
          pageRange: "",
        };
    }

    const parsed = JSON.parse(raw) as Partial<RagPopupConfig>;
    return {
      rules: Array.isArray(parsed.rules) ? parsed.rules : [],
      pageRange: typeof parsed.pageRange === "string" ? parsed.pageRange : "",
    };
  } catch (e) {
    Zotero.debug?.(`RAG: failed to load prefs: ${String(e)}`);
    return { rules: [], pageRange: "" };
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
        max-height: calc(100vh - 16px);
        overflow: auto;
        box-sizing: border-box;
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

      .rag-rules {
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-width: 0;
      }

      .rag-rule {
        display: grid;
        grid-template-columns: 24px 42px minmax(0, 1fr) 34px;
        gap: 8px;
        align-items: center;
        padding: 8px;
        min-width: 0;
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
        min-width: 0;
        max-width: 100%;
        box-sizing: border-box;
        resize: vertical;
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

      .rag-status {
        margin-top: 8px;
        min-height: 1.2em;
        opacity: 0.9;
      }

      .rag-page-range {
        margin-top: 10px;
      }

      .rag-page-range label {
        display: block;
        font-weight: 600;
        margin-bottom: 4px;
      }

      .rag-page-range input {
        width: 100%;
        border: 1px solid rgba(0,0,0,0.22);
        border-radius: 10px;
        background: transparent;
        color: inherit;
        padding: 7px 8px;
        outline: none;
        box-sizing: border-box;
      }
      .rag-page-range input:focus { border-color: rgba(0,0,0,0.38); }

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
      .rag-btn--danger {
        border-color: rgba(180,0,0,0.45);
      }
      .rag-btn--danger:hover {
        background: rgba(180,0,0,0.12);
      }
    `;
  safeAppend(doc, style);
}

function renderRules(popup: HTMLDivElement) {
  const rulesHost = popup.querySelector<HTMLDivElement>("#rag-rules")!;
  rulesHost.innerHTML = "";

  for (const rule of popupCfg.rules) {
    const row = popup.ownerDocument!.createElement("div");
    row.className = "rag-rule";
    row.dataset.ruleId = rule.id;

    row.innerHTML = `
          <input type="checkbox" class="rag-rule-enabled" title="Enable rule" />
          <input type="color" class="rag-color rag-rule-color" title="Rule color" />
          <textarea class="rag-rule-terms" placeholder="what to highlight"></textarea>
          <button type="button" class="rag-icon-btn" data-action="remove-rule" title="Remove rule">×</button>
        `;

    row.querySelector<HTMLInputElement>(".rag-rule-enabled")!.checked =
      rule.enabled;
    row.querySelector<HTMLInputElement>(".rag-rule-color")!.value =
      rule.colorHex;
    row.querySelector<HTMLTextAreaElement>(".rag-rule-terms")!.value =
      rule.termsRaw;

    rulesHost.appendChild(row);
  }

  const pageRangeInput =
    popup.querySelector<HTMLInputElement>("#rag-page-range");
  if (pageRangeInput) pageRangeInput.value = popupCfg.pageRange;
}

function readUiIntoConfig(popup: HTMLDivElement) {
  const ruleEls = Array.from<HTMLElement>(
    popup.querySelectorAll("#rag-rules [data-rule-id]"),
  );
  const rules: RagHighlightRule[] = ruleEls.map((el) => {
    const id = el.dataset.ruleId!;
    return {
      id,
      enabled: el.querySelector<HTMLInputElement>(".rag-rule-enabled")!.checked,
      colorHex: el.querySelector<HTMLInputElement>(".rag-rule-color")!.value,
      termsRaw: el.querySelector<HTMLTextAreaElement>(".rag-rule-terms")!.value,
    };
  });

  const pageRangeInput =
    popup.querySelector<HTMLInputElement>("#rag-page-range");
  popupCfg = {
    rules,
    pageRange: pageRangeInput?.value.trim() ?? "",
  };
}

function ensurePopup(doc: Document, reader: any): HTMLDivElement {
  const existing = doc.getElementById("rag-highlight-popup");
  if (existing) return existing as HTMLDivElement;
  const stopLabel = getString("stop-button-label");

  const popup = doc.createElement("div");
  popup.id = "rag-highlight-popup";
  popup.className = "rag-popup";

  popup.innerHTML = `
      <div class="rag-popup__header">
        <div class="rag-popup__title">Highlighting</div>
        <button type="button" class="rag-popup__close" id="rag-popup-close" aria-label="Close">×</button>
      </div>

      <div id="rag-rules" class="rag-rules"></div>
      <div class="rag-page-range">
        <label for="rag-page-range">Page range</label>
        <input id="rag-page-range" type="text" placeholder="e.g. 3 or 3-7" />
      </div>

      <div id="rag-status" class="rag-status" aria-live="polite"></div>
      <div class="rag-actions">
        <button type="button" class="rag-btn" id="rag-add-rule">+ Add rule</button>

        <div style="display:flex; gap:8px;">
          <button type="button" class="rag-btn" id="rag-save">Save</button>
          <button type="button" class="rag-btn rag-btn--danger" id="rag-stop" style="display:none;">${stopLabel}</button>
          <button type="button" class="rag-btn rag-btn--primary" id="rag-execute">Execute</button>
        </div>
      </div>
    `;

  safeAppend(doc, popup);

  const close = () => (popup.style.display = "none");

  popup
    .querySelector<HTMLButtonElement>("#rag-popup-close")!
    .addEventListener("click", close);

  popup.addEventListener("keydown", (e: KeyboardEvent) => {
    const target = e.target as Element | null;
    if (!target) return;

    // Keep reader-level key bindings from hijacking typing/edit keys in popup fields.
    if (target.closest("input, textarea, [contenteditable='true']")) {
      e.stopPropagation();
    }
  });

  if (!popup.dataset.ragDocBound) {
    popup.dataset.ragDocBound = "1";

    doc.addEventListener("keydown", (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    });

    doc.addEventListener("mousedown", (e: MouseEvent) => {
      if (isPopupVisible(popup) && !popup.contains(e.target as Node)) close();
    });
  }

  popup.addEventListener("click", (e) => {
    const target = e.target as HTMLElement;
    const removeBtn = target.closest(
      "[data-action='remove-rule']",
    ) as HTMLButtonElement | null;
    if (!removeBtn) return;

    const ruleEl = removeBtn.closest("[data-rule-id]") as HTMLElement | null;
    const ruleId = ruleEl?.dataset.ruleId;
    if (!ruleId) return;

    popupCfg.rules = popupCfg.rules.filter((r) => r.id !== ruleId);
    renderRules(popup);
  });

  popup
    .querySelector<HTMLButtonElement>("#rag-add-rule")!
    .addEventListener("click", () => {
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
    const stopBtn = popup.querySelector<HTMLButtonElement>("#rag-stop")!;
    const saveBtn = popup.querySelector<HTMLButtonElement>("#rag-save")!;
    const statusEl = popup.querySelector<HTMLElement>("#rag-status");
    const controller = createAbortControllerFromDoc(popup.ownerDocument!);
    activeExecuteAbortController = controller;

    stopBtn.style.display = controller ? "" : "none";
    stopBtn.disabled = !controller;
    stopBtn.onclick = () => {
      if (controller && !controller.signal.aborted) controller.abort();
    };

    try {
      executeBtn.disabled = true;
      saveBtn.disabled = true;
      let activeRequests: number | null = null;
      let baseStatus = "Working…";
      const renderStatus = () => {
        if (!statusEl) return;
        if (typeof activeRequests === "number") {
          statusEl.textContent = `${baseStatus} • Active requests: ${activeRequests}`;
        } else {
          statusEl.textContent = baseStatus;
        }
      };
      const setBaseStatus = (nextBaseStatus: string) => {
        baseStatus = nextBaseStatus;
        renderStatus();
      };
      const clearActiveRequests = () => {
        activeRequests = null;
        renderStatus();
      };
      renderStatus();

      readUiIntoConfig(popup);
      saveCfgToPrefs(popupCfg);

      const { RagClient } = await import("./ragClient");
      const { readCurrentPdf, createHighlightsFromAnalyzeResponse } =
        await import("./ragZoteroAnnotations");
      const pdfBlob = await readCurrentPdf(reader);
      const client = new RagClient();
      const request: RagConfig = {
        rules: popupCfg.rules
          .filter((r) => r.enabled)
          .map((r) => ({ id: r.id, termsRaw: r.termsRaw })),
        pageRange: popupCfg.pageRange || undefined,
      };
      let created = 0;
      const seen = new Set<string>();

      for await (const msg of client.analyzePdfStream(
        pdfBlob,
        request,
        controller?.signal,
      )) {
        if (msg.type === "error") {
          throw new Error(msg.message || "Annotation stream failed");
        }

        if (msg.type === "annotationConcurrency") {
          activeRequests = msg.activeRequests;
          renderStatus();
          continue;
        }

        if (msg.type === "updateProgress") {
          if (
            msg.stage === "marker_progress" &&
            typeof msg.chunk === "number" &&
            typeof msg.total === "number" &&
            msg.total > 0
          ) {
            if (
              typeof msg.marker === "number" &&
              typeof msg.markerTotal === "number" &&
              msg.markerTotal > 0
            ) {
              setBaseStatus(
                `Chunk ${msg.chunk}/${msg.total} • Marker ${msg.marker}/${msg.markerTotal}`,
              );
            } else {
              setBaseStatus(
                `Chunk ${msg.chunk}/${msg.total} • Processing markers…`,
              );
            }
          } else if (
            msg.stage === "chunk_started" &&
            typeof msg.chunk === "number" &&
            typeof msg.total === "number" &&
            msg.total > 0
          ) {
            setBaseStatus(`Chunk ${msg.chunk}/${msg.total}`);
          } else if (
            msg.stage === "chunk_dispatched" &&
            typeof msg.sent === "number" &&
            typeof msg.total === "number" &&
            msg.total > 0
          ) {
            setBaseStatus(`Sending chunks… (${msg.sent}/${msg.total})`);
          } else if (
            msg.stage === "chunk_processed" &&
            typeof msg.completed === "number" &&
            typeof msg.total === "number" &&
            msg.total > 0
          ) {
            setBaseStatus(`Processed chunks… (${msg.completed}/${msg.total})`);
          } else {
            setBaseStatus(`Working… (${msg.stage})`);
          }
          continue;
        }

        if (msg.type === "annotationMatches" && msg.matches.length > 0) {
          const unique = msg.matches.filter((m) => {
            const key = `${m.id}|${m.pageIndex}|${JSON.stringify(m.rects)}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
          if (unique.length > 0) {
            created += await createHighlightsFromAnalyzeResponse(reader, popupCfg, {
              matches: unique,
            });
            setBaseStatus(`Working… (${created} highlighted)`);
          }
          continue;
        }

        if (msg.type === "done") {
          break;
        }
      }
      reader._iframeWindow?.console?.log?.(
        `RAG: created ${created} annotations`,
      );
      clearActiveRequests();
      setBaseStatus(`Highlighted ${created} element${created === 1 ? "" : "s"}.`);
    } catch (e) {
      const maybeAbortError =
        !!e &&
        typeof e === "object" &&
        "name" in e &&
        (e as { name?: string }).name === "AbortError";
      if (maybeAbortError) {
        reader._iframeWindow?.console?.log?.("RAG: highlight execution stopped");
        clearActiveRequests();
        if (statusEl) statusEl.textContent = "Stopped.";
      } else {
        const msg = e instanceof Error ? e.message : String(e);
        Zotero.debug?.(`RAG execute failed: ${msg}`);
        reader._iframeWindow?.alert?.(`RAG failed: ${msg}`);
        clearActiveRequests();
        if (statusEl) statusEl.textContent = `Failed: ${msg}`;
      }
    } finally {
      if (activeExecuteAbortController === controller) {
        activeExecuteAbortController = null;
      }
      stopBtn.style.display = "none";
      stopBtn.onclick = null;
      executeBtn.disabled = false;
      saveBtn.disabled = false;
    }
  });

  return popup;
}

function openPopupNearButton(popup: HTMLDivElement, btn: HTMLElement) {
  popup.style.display = "block";

  const rect = btn.getBoundingClientRect();
  const margin = 8;

  const win = popup.ownerDocument!.defaultView!;
  const maxX = win.innerWidth - popup.offsetWidth - margin;
  const maxY = win.innerHeight - popup.offsetHeight - margin;

  popup.style.left = `${Math.max(margin, Math.min(rect.left, maxX))}px`;
  popup.style.top = `${Math.max(margin, Math.min(rect.bottom + margin, maxY))}px`;
}

type RenderToolbarEvent = {
  reader: any;
  doc: Document;
  params: object;
  append: (...nodes: Array<Node | string>) => void; // appendDOM
  type: "renderToolbar";
};
let toolbarHandler:
  | ((event: RenderToolbarEvent) => void | Promise<void>)
  | undefined;

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
    const svg = doc.createElementNS(svgNS, "svg") as unknown as SVGSVGElement;
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

  Zotero.Reader.registerEventListener(
    "renderToolbar",
    toolbarHandler,
    addon.data.config.addonID,
  );
}

export function unregisterReaderToolbarButton() {
  if (!toolbarHandler) return;
  Zotero.Reader.unregisterEventListener("renderToolbar", toolbarHandler);
  toolbarHandler = undefined;
}
