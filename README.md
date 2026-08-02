# obslink

Turn an `obsidian://` link into an `https://` link that works everywhere.

```
obsidian://open?vault=Knowledge%20Bank&file=Hubs%2FMoney
        │  obl
        ▼
https://obs.buildwithbos.com/#o=b2JzaWRpYW46Ly9vcGVuP3ZhdWx0PS4uLg
```

Paste that second link into a Google Calendar description, a Notion page, a
TickTick task, an email — anywhere. Clicking it opens the note in Obsidian.

## Why

Google Calendar (and Notion, TickTick, Gmail, Slack, most mobile clients) only
turns `http://` and `https://` into clickable links. An `obsidian://` URI pasted
into a description stays inert text. obslink is a static page that accepts the
`obsidian://` URI in its URL fragment and redirects to it.

## Your note names stay private

The URI is base64url-encoded into the **fragment** (`#o=…`). Browsers never
transmit the fragment to the server — it is not in the request line, not in the
logs, not in the `Referer` header. So the page is publicly hosted but never
learns which note you opened.

base64url is used because Google Calendar's linkifier truncates an auto-linked
URL at characters it does not consider part of a URL. A raw
`#vault=Knowledge Bank&file=…` would break on the space; the base64url alphabet
(`A–Z a–z 0–9 - _`) has nothing to break on.

## Use it

**Terminal** — `obl`, a [toolkit](https://github.com/BosTheCoder/toolkit) tool:

```sh
obl 'obsidian://open?vault=…&file=…'   # → https link
obl 'https://obs.buildwithbos.com/#o=…' # → obsidian URI (direction auto-detected)
obl                                     # reads the clipboard
obl -c                                  # also copies the result
obl --base https://…                    # override the host (env: OBSLINK_BASE)
```

In Obsidian, the source URI comes from the **Copy Obsidian URL** command.

**Browser** — open the page with no fragment and you get a paste box that does
the same conversion, both directions.

## Layout

| File | What it is |
|---|---|
| `index.html` | The page. Redirects when given `#o=…`, otherwise shows the converter. No build step, no dependencies. |
| `obslink.js` | The codec, for the page. |
| `obl.py` | The codec + CLI, for the terminal. Stdlib only. |
| `fixtures.json` | The contract between the two codecs. |

The codec exists twice because a no-backend design cannot share a runtime.
`fixtures.json` holds `(uri, token)` pairs that **both** test suites assert
against, in both directions — so a change that breaks compatibility fails the
other language's tests rather than silently producing links that only open on
one side.

`decode` refuses any payload that does not start with `obsidian://`. Without
that check the page would be an open redirect that borrows the trust of its own
domain.

## Tests

```sh
npm test                        # JS codec  (node --test)
python3 -m unittest test_obl -v # Python codec + CLI
```

## Hosting

GitHub Pages from `main`, custom domain via `CNAME`. It is a static file, so
anywhere that serves HTML works — `python3 -m http.server` locally, or a
Tailscale mount. `OBSLINK_BASE` points the CLI at whichever you use; the page
itself always builds links against the origin it was loaded from.

The repo is public. It holds no secrets and no note names — those exist only in
fragments, which are never sent anywhere.
