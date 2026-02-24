export const DEFAULT_API_BASE_URL = "http://localhost:8080";

export function normalizeApiBaseUrl(rawValue: string | undefined): string {
  return (rawValue || DEFAULT_API_BASE_URL).trim();
}

export function getExpectedWebDavUrl(apiBaseUrl: string): string {
  const apiBase = new URL(apiBaseUrl);
  return `${apiBase.host}/webdav`;
}
