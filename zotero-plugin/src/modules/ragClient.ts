import { getPref } from "../utils/prefs";

export interface QueryIn {
  prompt: string;
}

export interface Source {
  id: string;
  filename: string;
  zotero_id: string;
}

export interface QueryOut {
  response: string;
  sources: Source[];
}

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
    return getPref("apiBaseUrl" as any) || "http://localhost:8080";
  }

  public async query(prompt: string): Promise<QueryOut> {
    const url = `${this.baseUrl}/api/query`;
    const body: QueryIn = { prompt };

    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`RAG API error (${response.status}): ${errorText}`);
    }

    return (await response.json()) as QueryOut;
  }

  public async analyzePdf(pdf: string, cfg: RagConfig): Promise<RagAnalyzePdfResponse> {
    const win = Zotero.getMainWindow();
    const url = `${this.baseUrl}/api/annotations`;

    const fd = new win.FormData();
    fd.append("file", new win.Blob([pdf ], { type: "application/pdf" }), "document.pdf");
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
