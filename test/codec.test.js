import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { encode, decode, toHttps, fromHttps, describe as describeUri } from "../obslink.js";

const fixtures = JSON.parse(
  readFileSync(new URL("../fixtures.json", import.meta.url), "utf8"),
);

test("encodes each fixture to the agreed token", () => {
  for (const c of fixtures.cases) {
    assert.equal(encode(c.uri), c.token, c.name);
  }
});

test("decodes each agreed token back to its URI", () => {
  for (const c of fixtures.cases) {
    assert.equal(decode(c.token), c.uri, c.name);
  }
});

test("tokens contain only linkifier-safe characters", () => {
  for (const c of fixtures.cases) {
    assert.match(c.token, /^[A-Za-z0-9_-]+$/, c.name);
  }
});

test("round-trips through the https form", () => {
  for (const c of fixtures.cases) {
    assert.equal(fromHttps(toHttps(c.uri, fixtures.base)), c.uri, c.name);
  }
});

test("toHttps builds the fragment form against the given base", () => {
  const url = toHttps(fixtures.cases[0].uri, "https://example.test");
  assert.equal(url, `https://example.test/#o=${fixtures.cases[0].token}`);
});

test("toHttps tolerates a trailing slash on the base", () => {
  assert.equal(
    toHttps(fixtures.cases[0].uri, "https://example.test/"),
    toHttps(fixtures.cases[0].uri, "https://example.test"),
  );
});

test("rejects payloads that are not obsidian:// URIs", () => {
  for (const r of fixtures.rejected) {
    assert.throws(() => decode(r.token), r.name);
  }
});

test("toHttps refuses to wrap a non-obsidian:// URI", () => {
  assert.throws(() => toHttps("https://evil.example/login"));
  assert.throws(() => toHttps("javascript:alert(1)"));
});

test("fromHttps rejects a URL with no token", () => {
  assert.throws(() => fromHttps("https://obs.buildwithbos.com/"));
});

test("scheme check is case-insensitive", () => {
  const uri = "OBSIDIAN://open?vault=V&file=N";
  assert.equal(decode(encode(uri)), uri);
});

test("describe pulls vault and note for display", () => {
  const d = describeUri("obsidian://open?vault=Knowledge%20Bank&file=Hubs%2FMoney");
  assert.equal(d.vault, "Knowledge Bank");
  assert.equal(d.note, "Hubs/Money");
});

test("describe handles advanced-uri filepath", () => {
  const d = describeUri(fixtures.cases.find((c) => c.name === "advanced-uri").uri);
  assert.equal(d.note, "Inbox/Note.md");
});
