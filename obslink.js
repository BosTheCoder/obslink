// obslink codec — obsidian:// URI <-> https bounce URL.
//
// The obsidian:// URI is base64url-encoded into the bounce URL's *fragment*.
// Browsers never send the fragment to the server, so the note path stays on the
// device even though the page is publicly hosted. base64url is used because its
// alphabet (A-Z a-z 0-9 - _) contains nothing Google Calendar's linkifier will
// truncate on — a raw "?vault=Knowledge Bank&file=..." in a fragment does not
// survive being auto-linked.
//
// Mirrored in obl.py. fixtures.json is the contract between the two.

export const DEFAULT_BASE = "https://obs.buildwithbos.com";

const SCHEME = "obsidian://";

export function encode(uri) {
  const bytes = new TextEncoder().encode(uri);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function decode(token) {
  if (!/^[A-Za-z0-9_-]+$/.test(token)) throw new Error("not a valid obslink token");
  const b64 = token.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  const uri = new TextDecoder().decode(bytes);
  // The one security-critical line. Without it, #o=<base64 of javascript:...>
  // or of a phishing https:// target turns this page into an open redirect that
  // borrows the trust of its own domain.
  if (!uri.toLowerCase().startsWith(SCHEME)) {
    throw new Error("refusing to open a non-obsidian:// target");
  }
  return uri;
}

export function toHttps(uri, base = DEFAULT_BASE) {
  if (!uri.toLowerCase().startsWith(SCHEME)) {
    throw new Error("not an obsidian:// URI");
  }
  return `${base.replace(/\/+$/, "")}/#o=${encode(uri)}`;
}

export function fromHttps(url) {
  const m = /#o=([A-Za-z0-9_-]+)/.exec(url);
  if (!m) throw new Error("no obslink token in that URL");
  return decode(m[1]);
}

// Pull vault + note out of an obsidian:// URI for display. Best-effort: the URI
// is shown verbatim when it does not carry the params we know about.
export function describe(uri) {
  const q = uri.indexOf("?");
  if (q === -1) return { vault: null, note: null };
  const params = new URLSearchParams(uri.slice(q + 1));
  const note = params.get("file") ?? params.get("filepath") ?? params.get("query");
  return { vault: params.get("vault"), note };
}
