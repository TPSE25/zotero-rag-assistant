import type { RagAnalyzePdfResponse } from "./ragClient";
import { RagPopupConfig } from "./readerToolbar";

function pad(num: number, width: number) {
  const s = String(Math.max(0, Math.floor(num)));
  return s.length >= width ? s.slice(-width) : "0".repeat(width - s.length) + s;
}

function buildSortIndex(pageIndex: number, rects: number[][]): string {
  const y = rects?.[0]?.[1] ?? 0;
  const yInt = Math.max(0, Math.min(99999, Math.round(y)));
  return `${pad(pageIndex, 5)}|${pad(0, 6)}|${pad(yInt, 5)}`;
}

export async function readCurrentPdf(reader: any): Promise<string> {
  const attachment = await Zotero.Items.getAsync(reader.itemID);
  if (!attachment?.isAttachment?.() || !attachment?.isPDFAttachment?.()) {
    throw new Error("Current reader item is not a PDF attachment");
  }

  const path = attachment.getFilePath();
  if (!path)
    throw new Error(
      "PDF attachment has no local file path (linked file missing?)",
    );

  return await Zotero.File.getBinaryContentsAsync(path);
}

export async function createHighlightsFromAnalyzeResponse(
  reader: any,
  cfg: RagPopupConfig,
  resp: RagAnalyzePdfResponse,
): Promise<number> {
  const attachment: Zotero.Item = reader._item;

  let created = 0;

  for (const match of resp.matches) {
    const key = Zotero.Utilities.generateObjectKey();
    const now = new Date().toISOString();
    const annJson: any = {
      id: key,
      key,
      libraryID: attachment.libraryID,
      type: "highlight",
      readOnly: false,
      text: "",
      comment: "RAG",
      pageLabel: String(match.pageIndex + 1),
      color: cfg.rules.find((r) => r.id === match.id)?.colorHex,
      sortIndex: buildSortIndex(match.pageIndex, match.rects),
      position: { pageIndex: match.pageIndex, rects: match.rects },
      dateModified: now,
      relations: {},
    };
    await (Zotero.Annotations as any).saveFromJSON(attachment, annJson);
    created += 1;
  }

  return created;
}
