import { getPref } from "../utils/prefs";

export interface QueryIn {
  prompt: string;
}

export interface Source {
  id: string;
  filename: string;
  zotero_id: string;
}

export type QueryStreamMsg =
    | { type: "setSources"; sources: Source[] }
    | { type: "updateProgress"; stage: string; debug?: string; }
    | { type: "token"; token: string }
    | { type: "done" }

export type RagHighlightRule = {
  id: string;
  termsRaw: string;
};

export type RagConfig = {
  rules: RagHighlightRule[];
};

export type RagPdfMatch = {
  id: string;
  pageIndex: number;
  rects: number[][];
};

export type RagAnalyzePdfResponse = {
  matches: RagPdfMatch[];
};

export class RagClient {
  private get baseUrl(): string {
    return getPref("apiBaseUrl") || "http://localhost:8080";
  }

  public async *query(prompt: string): AsyncGenerator<QueryStreamMsg> {
    const url = `${this.baseUrl}/api/query`;
    const body: QueryIn = { prompt };

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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

  public async analyzePdf(pdf: string, cfg: RagConfig): Promise<RagAnalyzePdfResponse> {
    const win = Zotero.getMainWindow();
    const url = `${this.baseUrl}/api/annotations`;

    const fd = new win.FormData();
    const u8 = new win.Uint8Array(pdf.length);
    for (let i = 0; i < pdf.length; i++) {
      u8[i] = pdf.charCodeAt(i) & 0xff;
    }
    fd.append("file", new win.Blob([u8], { type: "application/pdf" }), "document.pdf");
    fd.append("config", JSON.stringify(cfg));

    const res = await fetch(url, {
      method: "POST",
      body: fd,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`RAG analyzePdf failed: HTTP ${res.status} ${res.statusText} ${body}`);
    }
    return (await res.json()) as RagAnalyzePdfResponse;
  }
}
