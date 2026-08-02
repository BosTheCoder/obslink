"""Tests for obl.py. Stdlib unittest — run with `python3 -m unittest test_obl -v`.

fixtures.json is shared with test/codec.test.js: the JS page and this CLI must
produce byte-identical tokens or a link made on one side breaks on the other.
"""
from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import obl

FIXTURES = json.loads((Path(__file__).parent / "fixtures.json").read_text(encoding="utf-8"))
CASES = FIXTURES["cases"]
REJECTED = FIXTURES["rejected"]
BASE = FIXTURES["base"]


class TestCodec(unittest.TestCase):
    def test_encodes_each_fixture_to_the_agreed_token(self):
        for c in CASES:
            with self.subTest(c["name"]):
                self.assertEqual(obl.encode(c["uri"]), c["token"])

    def test_decodes_each_agreed_token_back_to_its_uri(self):
        for c in CASES:
            with self.subTest(c["name"]):
                self.assertEqual(obl.decode(c["token"]), c["uri"])

    def test_tokens_contain_only_linkifier_safe_characters(self):
        for c in CASES:
            with self.subTest(c["name"]):
                self.assertRegex(c["token"], r"^[A-Za-z0-9_-]+$")

    def test_round_trips_through_the_https_form(self):
        for c in CASES:
            with self.subTest(c["name"]):
                self.assertEqual(obl.from_https(obl.to_https(c["uri"], BASE)), c["uri"])

    def test_to_https_builds_the_fragment_form(self):
        self.assertEqual(
            obl.to_https(CASES[0]["uri"], "https://example.test"),
            f"https://example.test/#o={CASES[0]['token']}",
        )

    def test_to_https_tolerates_a_trailing_slash_on_the_base(self):
        self.assertEqual(
            obl.to_https(CASES[0]["uri"], "https://example.test/"),
            obl.to_https(CASES[0]["uri"], "https://example.test"),
        )

    def test_rejects_payloads_that_are_not_obsidian_uris(self):
        for r in REJECTED:
            with self.subTest(r["name"]), self.assertRaises(obl.OblError):
                obl.decode(r["token"])

    def test_to_https_refuses_to_wrap_a_non_obsidian_uri(self):
        for bad in ("https://evil.example/login", "javascript:alert(1)"):
            with self.subTest(bad), self.assertRaises(obl.OblError):
                obl.to_https(bad)

    def test_scheme_check_is_case_insensitive(self):
        uri = "OBSIDIAN://open?vault=V&file=N"
        self.assertEqual(obl.decode(obl.encode(uri)), uri)


class TestConvert(unittest.TestCase):
    def test_detects_obsidian_uri_and_goes_outbound(self):
        self.assertEqual(obl.convert(CASES[0]["uri"], BASE), obl.to_https(CASES[0]["uri"], BASE))

    def test_detects_obslink_url_and_goes_inbound(self):
        url = obl.to_https(CASES[0]["uri"], BASE)
        self.assertEqual(obl.convert(url, BASE), CASES[0]["uri"])

    def test_tolerates_surrounding_whitespace(self):
        self.assertEqual(
            obl.convert(f"  {CASES[0]['uri']}\n", BASE), obl.to_https(CASES[0]["uri"], BASE)
        )

    def test_rejects_unrecognised_input(self):
        with self.assertRaises(obl.OblError):
            obl.convert("just some text", BASE)

    def test_rejects_empty_input(self):
        with self.assertRaises(obl.OblError):
            obl.convert("   ", BASE)


class TestCli(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = obl.main(argv)
        return code, out.getvalue().strip(), err.getvalue().strip()

    def test_prints_the_https_link_and_exits_zero(self):
        code, out, _ = self._run([CASES[0]["uri"], "--base", BASE])
        self.assertEqual(code, 0)
        self.assertEqual(out, obl.to_https(CASES[0]["uri"], BASE))

    def test_base_flag_overrides_the_default_host(self):
        _, out, _ = self._run([CASES[0]["uri"], "--base", "https://example.test"])
        self.assertTrue(out.startswith("https://example.test/#o="))

    def test_base_falls_back_to_the_env_var(self):
        with mock.patch.dict("os.environ", {"OBSLINK_BASE": "https://from-env.test"}):
            _, out, _ = self._run([CASES[0]["uri"]])
        self.assertTrue(out.startswith("https://from-env.test/#o="))

    def test_bad_input_exits_non_zero_with_a_message_on_stderr(self):
        code, out, err = self._run(["not a link"])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("obl:"))

    def test_reads_the_clipboard_when_given_no_argument(self):
        with mock.patch.object(obl, "clipboard_read", return_value=CASES[0]["uri"]):
            code, out, _ = self._run(["--base", BASE])
        self.assertEqual(code, 0)
        self.assertEqual(out, obl.to_https(CASES[0]["uri"], BASE))

    def test_copy_flag_writes_the_result_to_the_clipboard(self):
        with mock.patch.object(obl, "clipboard_write", return_value=True) as w:
            code, out, _ = self._run([CASES[0]["uri"], "-c", "--base", BASE])
        self.assertEqual(code, 0)
        w.assert_called_once_with(out)

    def test_copy_failure_is_reported_and_exits_non_zero(self):
        with mock.patch.object(obl, "clipboard_write", return_value=False):
            code, out, err = self._run([CASES[0]["uri"], "-c", "--base", BASE])
        self.assertEqual(code, 1)
        self.assertEqual(out, obl.to_https(CASES[0]["uri"], BASE))
        self.assertIn("clipboard", err)


class TestClipboardFallback(unittest.TestCase):
    def test_read_prefers_wl_paste_then_falls_back_to_powershell(self):
        with mock.patch.object(obl, "_run", side_effect=[None, "from-windows"]) as r:
            self.assertEqual(obl.clipboard_read(), "from-windows")
        self.assertEqual(r.call_args_list[0].args[0][0], "wl-paste")
        self.assertEqual(r.call_args_list[1].args[0][0], "powershell.exe")

    def test_read_raises_when_no_clipboard_tool_works(self):
        with mock.patch.object(obl, "_run", return_value=None), self.assertRaises(obl.OblError):
            obl.clipboard_read()

    def test_write_prefers_wl_copy_then_falls_back_to_clip_exe(self):
        with mock.patch.object(obl, "_run", side_effect=[None, ""]) as r:
            self.assertTrue(obl.clipboard_write("x"))
        self.assertEqual(r.call_args_list[0].args[0][0], "wl-copy")
        self.assertEqual(r.call_args_list[1].args[0][0], "clip.exe")

    def test_write_returns_false_when_nothing_works(self):
        with mock.patch.object(obl, "_run", return_value=None):
            self.assertFalse(obl.clipboard_write("x"))


if __name__ == "__main__":
    unittest.main()
