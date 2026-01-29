const getZoteroPane = () =>
    (Zotero as any).getActiveZoteroPane?.();

const resolveItem = (zoteroId: string) => {
    const libID = (Zotero.Libraries?.userLibraryID ?? 0);
    return Zotero.Items.getByLibraryAndKeyAsync(libID, zoteroId);
};

export const showZoteroSource = async (zoteroId: string, open: boolean) => {
    const pane = getZoteroPane();
    if (!pane) throw new Error("ZoteroPane not available");

    let item: any = await resolveItem(zoteroId);
    if (!item) return;

    try {
        pane.selectItem?.(item.id);
    } catch (e: any) {
        Zotero.logError?.(e);
    }

    if (!item.isAttachment?.()) {
        const best = await item.getBestAttachment();
        if (best) item = best;
    }

    if (open && typeof pane.viewAttachment === "function") {
        await pane.viewAttachment(item.id);
        return;
    }

    const key = item.key ?? zoteroId;
    if (open && key) {
        Zotero.launchURL(`zotero://open-pdf/library/items/${key}`);
    }
};