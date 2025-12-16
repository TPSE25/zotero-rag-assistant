function insertMenu(win: _ZoteroTypes.MainWindow) {
  const doc = win.top!.document; // 🔥 THIS IS THE FIX

  const toolsPopup = doc.getElementById("menu_ToolsPopup");
  if (!toolsPopup) {
    Zotero.debug("❌ Tools menu popup not found in top document");
    return;
  }

  if (doc.getElementById("zoteroragtemplate-ai-chat")) {
    return;
  }

  const item = doc.createXULElement("menuitem");
  item.id = "zoteroragtemplate-ai-chat";
  item.setAttribute("label", "AI Chat");

  item.addEventListener("command", () => {
    win.openDialog(
      "chrome://zoteroragtemplate/content/chat.html",
      "zotero-rag-chat",
      "chrome,centerscreen,resizable",
    );
  });

  toolsPopup.appendChild(item);
  Zotero.debug("✅ AI Chat menu item added");
}

export default {
  async onStartup() {},

  async onMainWindowLoad(win: _ZoteroTypes.MainWindow) {
    insertMenu(win);
  },

  async onMainWindowUnload() {},
  async onShutdown() {},
};
