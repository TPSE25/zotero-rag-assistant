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
}
