import { getString } from "../utils/locale";
import { getPref } from "../utils/prefs";
import { normalizeApiBaseUrl } from "../utils/serverConfig";

type PromptPlaceholder = {
  name: string;
  description: string;
};

type SystemPrompt = {
  key: string;
  title: string;
  description: string;
  placeholders: PromptPlaceholder[];
  content: string;
};

type SystemPromptListResponse = {
  prompts: SystemPrompt[];
};

export async function initPromptSettings(window: Window): Promise<void> {
  const doc = window.document;
  const reloadBtn = doc.getElementById("ragPromptsReloadBtn");
  const saveBtn = doc.getElementById("ragPromptsSaveBtn");
  const statusEl = doc.getElementById("ragPromptsStatus");
  if (!reloadBtn || !saveBtn || !statusEl) return;

  const promptKeys = [
    "query_system",
    "title_system",
    "annotation_coarse_user",
    "annotation_boundary_user",
  ] as const;

  const getApiBase = () => normalizeApiBaseUrl(getPref("apiBaseUrl"));
  const setStatus = (message: string) => {
    statusEl.textContent = message;
  };

  const renderPlaceholders = (prompt: SystemPrompt) => {
    const helpEl = doc.getElementById(`ragPromptHelp-${prompt.key}`);
    if (!helpEl) return;
    helpEl.replaceChildren();

    const addLine = (text: string) => {
      const row = doc.createElement("div");
      row.classList.add("rag-placeholder-item");
      row.textContent = text;
      helpEl.appendChild(row);
    };

    if (!prompt.placeholders.length) {
      addLine(getString("pref-prompts-no-placeholders"));
      return;
    }

    addLine(getString("pref-prompts-placeholder-prefix"));
    for (const placeholder of prompt.placeholders) {
      addLine(`{{${placeholder.name}}}: ${placeholder.description}`);
    }
  };

  const loadPrompts = async () => {
    try {
      setStatus(getString("pref-prompts-status-loading"));
      const res = await fetch(`${getApiBase()}/api/system-prompts`);
      if (!res.ok) {
        const err = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status} ${err}`.trim());
      }
      const data = (await res.json()) as unknown as SystemPromptListResponse;
      const byKey = new Map(data.prompts.map((p) => [p.key, p] as const));
      for (const key of promptKeys) {
        const prompt = byKey.get(key);
        const input = doc.getElementById(
          `ragPrompt-${key}`,
        ) as HTMLTextAreaElement | null;
        if (!input || !prompt) continue;
        input.value = prompt.content;
        renderPlaceholders(prompt);
      }
      setStatus(getString("pref-prompts-status-loaded"));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus(
        getString("pref-prompts-status-load-error", { args: { message: msg } }),
      );
    }
  };

  const savePrompts = async () => {
    try {
      const base = getApiBase();
      for (const key of promptKeys) {
        const input = doc.getElementById(
          `ragPrompt-${key}`,
        ) as HTMLTextAreaElement | null;
        if (!input) continue;
        const res = await fetch(`${base}/api/system-prompts/${key}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: input.value }),
        });
        if (!res.ok) {
          const err = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status} ${err}`.trim());
        }
      }
      setStatus(getString("pref-prompts-status-saved"));
      await loadPrompts();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus(
        getString("pref-prompts-status-save-error", { args: { message: msg } }),
      );
    }
  };

  reloadBtn.addEventListener("click", () => void loadPrompts());
  saveBtn.addEventListener("click", () => void savePrompts());
  await loadPrompts();
}
