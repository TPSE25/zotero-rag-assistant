import { getPref } from "../utils/prefs";
import { normalizeApiBaseUrl } from "../utils/serverConfig";

export interface QueryIn {
  prompt: string;
  messages?: ChatTitleMessage[];
  sources?: Source[];
}

export interface ChatTitleMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatTitleIn {
  messages: ChatTitleMessage[];
}

export interface ChatTitleOut {
  title: string | null;
}

export interface Source {
  id: string;
  filename: string;
  zotero_id: string;
  pages?: number[];
}

export type QueryStreamMsg =
  | { type: "setSources"; sources: Source[] }
  | { type: "updateProgress"; stage: string; debug?: string }
  | { type: "token"; token: string }
  | { type: "done" };

export type RagHighlightRule = {
  id: string;
  termsRaw: string;
};

export type RagConfig = {
  rules: RagHighlightRule[];
  pageRange?: string;
};

export type RagPdfMatch = {
  id: string;
  pageIndex: number;
  rects: number[][];
  text?: string | null;
};

export type RagAnalyzePdfResponse = {
  matches: RagPdfMatch[];
};

export type AnnotationProgressEvent = {
  type: "updateProgress";
  stage: string;
  sent?: number;
  chunk?: number;
  marker?: number;
  markerTotal?: number;
  markerId?: string;
  completed?: number;
  total?: number;
};

export type AnnotationStreamMsg =
  | {
      type: "updateProgress";
      stage: string;
      debug?: string;
      sent?: number;
      chunk?: number;
      marker?: number;
      markerTotal?: number;
      markerId?: string;
      completed?: number;
      total?: number;
    }
  | { type: "annotationConcurrency"; activeRequests: number }
  | { type: "annotationMatches"; matches: RagPdfMatch[] }
  | { type: "error"; message: string }
  | { type: "done" };

export class RagClient {
  private get baseUrl(): string {
    return normalizeApiBaseUrl(getPref("apiBaseUrl"));
  }

  public async *query(
    prompt: string,
    messages?: ChatTitleMessage[],
    sources?: Source[],
    signal?: AbortSignal,
  ): AsyncGenerator<QueryStreamMsg> {
    const url = `${this.baseUrl}/api/query`;
    const body: QueryIn = { prompt, messages, sources };
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`RAG API error (${response.status}): ${errorText}`);
    }
    if (!response.body) {
      throw new Error("Streaming not supported: response.body is null");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      // @ts-expect-error zotero/gecko types: getReader() ends up as BYOB
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        yield JSON.parse(trimmed) as QueryStreamMsg;
      }
    }
    const tail = buf.trim();
    if (tail) yield JSON.parse(tail) as QueryStreamMsg;
  }

  public async analyzePdf(
    pdf: string,
    cfg: RagConfig,
    signal?: AbortSignal,
    onProgress?: (event: AnnotationProgressEvent) => void,
    onMatches?: (matches: RagPdfMatch[]) => void,
  ): Promise<RagAnalyzePdfResponse> {
    const allMatches: RagPdfMatch[] = [];
    for await (const msg of this.analyzePdfStream(pdf, cfg, signal)) {
      if (msg.type === "error") {
        throw new Error(msg.message || "Annotation stream failed");
      }
      if (msg.type === "updateProgress" && onProgress) {
        onProgress(msg);
      }
      if (msg.type === "annotationMatches") {
        allMatches.push(...msg.matches);
        if (onMatches) onMatches(msg.matches);
      }
    }
    return { matches: allMatches };
  }

  public async *analyzePdfStream(
    pdf: string,
    cfg: RagConfig,
    signal?: AbortSignal,
  ): AsyncGenerator<AnnotationStreamMsg> {
    const win = Zotero.getMainWindow();
    const url = `${this.baseUrl}/api/annotations`;
    const fd = new win.FormData();
    const u8 = new win.Uint8Array(pdf.length);
    for (let i = 0; i < pdf.length; i++) {
      u8[i] = pdf.charCodeAt(i) & 0xff;
    }
    fd.append(
      "file",
      new win.Blob([u8], { type: "application/pdf" }),
      "document.pdf",
    );
    fd.append("config", JSON.stringify(cfg));

    const res = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/x-ndjson" },
      body: fd,
      signal,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(
        `RAG analyzePdf failed: HTTP ${res.status} ${res.statusText} ${body}`,
      );
    }
    if (!res.body) {
      throw new Error(
        "Streaming not supported for /api/annotations: response.body is null",
      );
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";

    while (true) {
      // @ts-expect-error zotero/gecko types: getReader() ends up as BYOB
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        yield JSON.parse(trimmed) as AnnotationStreamMsg;
      }
    }

    const tail = buf.trim();
    if (tail) yield JSON.parse(tail) as AnnotationStreamMsg;
  }

  public async generateChatTitle(
    messages: ChatTitleMessage[],
  ): Promise<string | null> {
    const url = `${this.baseUrl}/api/chat-title`;
    const body: ChatTitleIn = { messages };
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const errorText = await res.text().catch(() => "");
      throw new Error(`RAG title API error (${res.status}): ${errorText}`);
    }
    const out = (await res.json()) as unknown as ChatTitleOut;
    const title = (out?.title ?? "").trim();
    return title || null;
  }
}
