# obslink — design

**Date:** 2026-08-02
**Status:** Approved-by-default (built under stated assumptions; see Open Questions)

## Problem

`obsidian://` URIs are the only way to deep-link into the Knowledge Bank vault,
but most applications refuse to render them. Google Calendar event descriptions
are the motivating case: the linkifier only turns `http://` and `https://` into
anchors, so an `obsidian://` URI pasted there stays inert text. The same happens
in Notion, TickTick, Gmail, Slack, and most mobile clients.

Goal: given an `obsidian://` URI, produce an `https://` URI that is clickable
everywhere and, when clicked, opens the note in Obsidian.

## Approach

A single static page acts as a bounce point. The `obsidian://` URI is
base64url-encoded into the page's **URL fragment**. Clicking the `https://` link
loads the page, which decodes the fragment and navigates to the `obsidian://`
URI, handing off to the Obsidian app.

```
obsidian://open?vault=Knowledge%20Bank&file=Hubs%2FMoney
        │
        │  obl  (or the page's paste box)
        ▼
https://obs.buildwithbos.com/#o=b2JzaWRpYW46Ly9vcGVuP3ZhdWx0PS4uLg
        │
        │  click, anywhere
        ▼
   static page loads → decodes #fragment → location.replace(obsidian://…)
        │
        ▼
   Obsidian opens the note
```

### Why the fragment, not the path or query

Browsers never transmit the fragment to the server. It is not in the request
line, so it cannot appear in GitHub's access logs, in any middlebox, or in a
`Referer` header. The note path therefore stays on the device even though the
page itself is publicly hosted. A path- or query-based scheme
(`/n?file=Hubs/Money`) would leak every note title to the host.

### Why base64url

The token must survive Google Calendar's linkifier, which terminates an
auto-linked URL at characters it does not consider part of a URL. Raw
`?vault=Knowledge%20Bank&file=…` inside a fragment risks truncation on the
space, `&`, or `/`. The base64url alphabet (`A–Z a–z 0–9 - _`) with padding
stripped contains nothing a linkifier will break on.

### Why GitHub Pages, not Fly

The page is one static HTML file with no backend. GitHub Pages serves it free,
always-on, with no cold start. The Fly `static` stack from `demo-tools` would
work but wraps Vite + React + nginx in a Docker image and auto-stops, adding a
~5s wake-up to a link whose entire job is to redirect instantly. Pages is the
smaller, faster fit.

The repo is public. This is safe: it contains no secrets, and no note names —
those exist only in fragments, which are never sent anywhere.

## Components

Three units, each independently testable.

### 1. `obslink.js` — the codec (browser)

Pure functions, no DOM access, no I/O.

- `encode(uri) -> token` — UTF-8 bytes → base64url, padding stripped.
- `decode(token) -> uri` — inverse; throws on malformed input.
- `toHttps(uri, base) -> url`
- `fromHttps(url) -> uri`

`decode` enforces that the result begins with `obsidian://` (case-insensitive).
Without that check the page is an **open redirect**: anyone could craft
`#o=<base64 of javascript:…>` or a phishing `https://` target and send a link
that appears to come from a trusted domain. The scheme allowlist is the single
security-critical line in the project.

### 2. `index.html` — the page

Self-contained, no build step, no dependencies. Two modes decided by whether
the fragment is present:

**Redirect mode** (`#o=…` present):
1. Decode and validate. On failure, render the error and navigate nowhere.
2. Render the decoded target (vault + note path) so the destination is visible
   before the handoff.
3. `location.replace(uri)` immediately.
4. Leave an "Open in Obsidian" button on screen. Mobile browsers sometimes
   suppress a custom-scheme navigation that lacks a user gesture; the button is
   the fallback and costs nothing when the auto-redirect works.

`location.replace`, not `location.href`, so the bounce page does not land in
history and Back returns to the calendar.

**Converter mode** (no fragment): a paste box. Paste an `obsidian://` URI, get
the `https://` link with a Copy button. Paste an obslink `https://` URL and it
decodes back — direction is auto-detected from the input.

Dark and light theme via `prefers-color-scheme`.

### 3. `obl` — the toolkit command

A `toolkit` tool at `tools/other/obl/`, stdlib-only Python behind an `entry.sh`
wrapper, matching the `serve-index` layout.

```
obl <obsidian-uri>     → prints the https link
obl <obslink-url>      → prints the obsidian URI   (direction auto-detected)
obl                    → reads the clipboard
obl -c                 → also copy the result to the clipboard
obl --base <url>       → override the host (env: OBSLINK_BASE)
```

Output goes to stdout unadorned so the command pipes cleanly; `-c` is opt-in.
Clipboard uses `wl-copy`/`wl-paste`, falling back to `clip.exe` and
`powershell.exe Get-Clipboard` under WSL.

### Keeping the two codecs honest

The codec exists twice — once in JavaScript for the page, once in Python for the
CLI — because a no-backend design cannot share a runtime. They will drift unless
something forces them not to.

`fixtures.json` holds `(uri, token)` pairs, including non-ASCII vault names,
spaces, and nested paths. Both test suites read the same file and assert both
directions. A change to either implementation that breaks compatibility fails
the other language's tests.

## Testing

- **Codec (both languages):** shared fixtures, round-trip properties, and
  rejection of non-`obsidian://` payloads.
- **CLI:** direction auto-detection, base override, clipboard fallback ordering,
  malformed input exits non-zero with a message on stderr.
- **Page:** a Playwright check that loading `#o=<token>` attempts navigation to
  the right `obsidian://` URI, and that a hostile payload renders an error and
  navigates nowhere.

## Deployment

1. Public GitHub repo `BosTheCoder/obslink`, Pages served from `main` at root.
2. `CNAME` file → `obs.buildwithbos.com`.
3. Cloudflare DNS: `CNAME obs → bosthecoder.github.io`, **DNS-only** (grey
   cloud) so GitHub can issue the certificate. A `CLOUDFLARE_API_TOKEN` is
   already present in `~/.env`, so this step is scriptable.

`https://bosthecoder.github.io/obslink/` works immediately and is the fallback
if the custom domain is not wanted. `OBSLINK_BASE` switches the CLI between
them, so the choice is not baked in.

## Out of scope

- **Short links** (`/n/money`). Needs a backend and a stored mapping, and would
  put note titles on the server — the thing the fragment design exists to avoid.
- **Building URIs from note paths** (`obl --file "Hubs/Money.md"`). Obsidian's
  built-in "Copy Obsidian URL" already produces the input this tool consumes.
- **A useful fallback when Obsidian is not installed.** The page shows the note
  path and stops. Nothing better is possible without serving note content.

Advanced URI links need no special handling: the codec is scheme-agnostic below
`obsidian://`, so `obsidian://advanced-uri?…` round-trips like any other.

## Open questions

Built on these assumptions, each cheap to reverse:

1. **Public GitHub Pages** over Tailscale-on-Bos-Desktop. Tailscale keeps
   everything private but a link in a calendar entry is dead whenever the
   desktop sleeps or Tailscale is off — the exact moment it is most needed.
2. **Both interfaces** (CLI and paste box) rather than one. The page is hosted
   regardless and the codec is shared, so the second interface is nearly free.
3. **`obs.buildwithbos.com`** as the hostname. Short matters here — the URL is
   read and pasted by a human.
