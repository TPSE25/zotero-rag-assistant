import { config } from "../../package.json";
import {getString} from "./locale";

type PluginPrefsMap = _ZoteroTypes.Prefs["PluginPrefsMap"];

const PREFS_PREFIX = config.prefsPrefix;

/**
 * @param key
 */
export function getPref<K extends keyof PluginPrefsMap>(key: K) {
  return Zotero.Prefs.get(`${PREFS_PREFIX}.${key}`, true) as PluginPrefsMap[K];
}

/**
 * @param key
 * @param value
 */
export function setPref<K extends keyof PluginPrefsMap>(
  key: K,
  value: PluginPrefsMap[K],
) {
  return Zotero.Prefs.set(`${PREFS_PREFIX}.${key}`, value, true);
}

/**
 * @param key
 */
export function clearPref(key: string) {
  return Zotero.Prefs.clear(`${PREFS_PREFIX}.${key}`, true);
}

export function checkWebDAVOnStart() {
  const enabled  = Zotero.Prefs.get("sync.storage.enabled");
  const protocol = Zotero.Prefs.get("sync.storage.protocol");
  const scheme   = Zotero.Prefs.get("sync.storage.scheme");
  const url      = Zotero.Prefs.get("sync.storage.url");

  const expected = {
    protocol: "webdav",
    scheme: "http",
    url: "localhost:8080/webdav",
  };

  const empty = getString("webdav-check-empty");

  const problems: string[] = [];

  if (!enabled) {
    problems.push(getString("webdav-check-disabled"));
  }

  if (protocol !== expected.protocol) {
    problems.push(
        getString("webdav-check-protocol-mismatch", {
          args: { actual: protocol ?? empty, expected: expected.protocol },
        }),
    );
  }

  if (scheme !== expected.scheme) {
    problems.push(
        getString("webdav-check-scheme-mismatch", {
          args: { actual: scheme ?? empty, expected: expected.scheme },
        }),
    );
  }

  if (url !== expected.url) {
    problems.push(
        getString("webdav-check-url-mismatch", {
          args: { actual: url ?? empty, expected: expected.url },
        }),
    );
  }

  if (problems.length === 0) return;

  const problemsText = problems.map((p) => `• ${p}`).join("\n");

  const msg = getString("webdav-check-dialog-body", {
    args: { problems: problemsText },
  });

  const buttonFlags =
      Services.prompt.BUTTON_POS_0! * Services.prompt.BUTTON_TITLE_IS_STRING! +
      Services.prompt.BUTTON_POS_1! * Services.prompt.BUTTON_TITLE_IS_STRING! +
      Services.prompt.BUTTON_POS_0_DEFAULT!;

  const choice = Services.prompt.confirmEx(
      Zotero.getMainWindow() as unknown as mozIDOMWindowProxy,
      getString("webdav-check-dialog-title"),
      msg,
      buttonFlags,
      getString("webdav-check-open-settings"),
      getString("webdav-check-not-now"),
      "",
      "",
      { value: false }, /* unused */
  );

  if (choice === 0) {
    Zotero.Utilities.Internal.openPreferences("zotero-prefpane-sync");
  }

}
