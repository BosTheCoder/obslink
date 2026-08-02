#!/usr/bin/env python3
"""obl — turn an obsidian:// URI into an https link that works everywhere.

Google Calendar (and Notion, TickTick, Gmail, Slack, most mobile clients) only
linkify http(s) URLs, so an obsidian:// URI pasted into a description stays
inert text. This wraps it in an https link to a static bounce page that
redirects back to obsidian://.

The URI rides in the URL *fragment*, which browsers never send to the server, so
the note path stays on the device even though the page is publicly hosted.

    obl <obsidian-uri>   ->  https://obs.buildwithbos.com/#o=<token>
    obl <obslink-url>    ->  obsidian://...            (direction auto-detected)
    obl                  ->  reads the clipboard
    obl -c               ->  also copy the result to the clipboard

Stdlib only. Mirrors obslink.js; fixtures.json is the contract between the two.
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys

DEFAULT_BASE = "https://obs.buildwithbos.com"
SCHEME = "obsidian://"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]+$")
TOKEN_IN_URL_RE = re.compile(r"#o=([A-Za-z0-9_-]+)")


class OblError(Exception):
    """Anything the user should see as a one-line message, not a traceback."""


def encode(uri: str) -> str:
    return base64.urlsafe_b64encode(uri.encode("utf-8")).decode("ascii").rstrip("=")


def decode(token: str) -> str:
    if not TOKEN_RE.match(token):
        raise OblError("not a valid obslink token")
    pad = "=" * (-len(token) % 4)
    try:
        uri = base64.urlsafe_b64decode(token + pad).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise OblError(f"could not decode token: {exc}") from exc
    # The one security-critical check. Without it a crafted token turns the
    # bounce page into an open redirect that borrows its own domain's trust.
    if not uri.lower().startswith(SCHEME):
        raise OblError("refusing to open a non-obsidian:// target")
    return uri


def to_https(uri: str, base: str = DEFAULT_BASE) -> str:
    if not uri.lower().startswith(SCHEME):
        raise OblError("not an obsidian:// URI")
    return f"{base.rstrip('/')}/#o={encode(uri)}"


def from_https(url: str) -> str:
    m = TOKEN_IN_URL_RE.search(url)
    if not m:
        raise OblError("no obslink token in that URL")
    return decode(m.group(1))


def convert(text: str, base: str = DEFAULT_BASE) -> str:
    """Auto-detect direction: obsidian:// goes out, an obslink URL comes back."""
    text = text.strip()
    if not text:
        raise OblError("nothing to convert")
    if text.lower().startswith(SCHEME):
        return to_https(text, base)
    if TOKEN_IN_URL_RE.search(text):
        return from_https(text)
    raise OblError(
        "expected an obsidian:// URI or an obslink https URL, got:\n  "
        + (text[:120] + "..." if len(text) > 120 else text)
    )


# --- clipboard ---------------------------------------------------------------
# wl-clipboard first (the Wayland session), then the Windows host under WSL.

def _run(cmd: list[str], *, text_in: str | None = None) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(
            cmd, input=text_in, capture_output=True, text=True, timeout=5, check=True
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout


def clipboard_read() -> str:
    for cmd in (
        ["wl-paste", "--no-newline"],
        ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
    ):
        got = _run(cmd)
        if got:
            return got
    raise OblError("could not read the clipboard (install wl-clipboard, or pass the link as an argument)")


def clipboard_write(text: str) -> bool:
    for cmd in (["wl-copy"], ["clip.exe"]):
        if _run(cmd, text_in=text) is not None:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="obl",
        description="Convert an obsidian:// URI to a shareable https link (and back).",
    )
    p.add_argument("link", nargs="?", help="obsidian:// URI or obslink URL (default: clipboard)")
    p.add_argument("-c", "--copy", action="store_true", help="copy the result to the clipboard")
    p.add_argument(
        "--base",
        default=os.environ.get("OBSLINK_BASE", DEFAULT_BASE),
        help=f"bounce-page base URL (env: OBSLINK_BASE, default: {DEFAULT_BASE})",
    )
    args = p.parse_args(argv)

    try:
        text = args.link if args.link is not None else clipboard_read()
        result = convert(text, args.base)
    except OblError as exc:
        print(f"obl: {exc}", file=sys.stderr)
        return 1

    print(result)
    if args.copy and not clipboard_write(result):
        print("obl: could not copy to the clipboard", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
