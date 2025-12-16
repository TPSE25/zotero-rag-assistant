import Addon from "./addon";
import hooks from "./hooks";

// Ensure Zotero.Zotero exists (it does in Zotero 7)
const zoteroRoot = Zotero as any;

// Create addon instance
const addon = new Addon();

// Attach hooks (bootstrap.js requires this)
(addon as any).hooks = hooks;

// Expose addon EXACTLY where scaffold expects it
zoteroRoot.Zotero = zoteroRoot.Zotero || {};
zoteroRoot.Zotero.ZoteroRAGPluginTemplate = addon;
