"""Contract for `tools/kg-mcp`, the opt-in read-only MCP server over the knowledge-graph index.

A tiny repository is indexed with `tools/kg init` into a temp MAGICIAN_HOME, then the server is
driven over stdin/stdout as a subprocess, one newline-delimited JSON-RPC message per line. Checked:
the legacy era (`initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`), the
modern era (`server/discover` and per-request `_meta`, `resultType`, version errors), that the era
is chosen per request and never inferred from an earlier one, the tool list (at most 5 tools, all
named `kg_*`, read-only annotations, input and output schemas), `structuredContent` against the
`outputSchema`, stateless cursors that a second server process accepts, actionable `isError`
results (no index, unknown target, bad arguments, bad cursor), protocol errors (parse error, invalid
request, unknown method, unknown tool), the read-only guarantee (index files and repository
unchanged, `mode=ro` + `query_only` refuse writes), and that the plugin does not register the
server. Stdlib only; no network.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from importlib.machinery import SourceFileLoader
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
KG = ROOT / "tools" / "kg"
SERVER = ROOT / "tools" / "kg-mcp"
MODERN = "2026-07-28"
META = {"io.modelcontextprotocol/protocolVersion": MODERN,
        "io.modelcontextprotocol/clientCapabilities": {},
        "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"}}

FILES = {
    "util.py": "def helper():\n    return 1\n",
    "app.py": "from util import helper\n\n\ndef main():\n    return helper()\n",
    "parsers.py": "".join(f"def parse_{w}(text):\n    return text\n\n\n"
                          for w in ("alpha", "beta", "gamma", "delta", "epsilon")),
}


def env_for(home: Path) -> dict:
    git = shutil.which("git")
    path = os.pathsep.join(dict.fromkeys(([os.path.dirname(git)] if git else []) + ["/usr/bin", "/bin"]))
    return {"PATH": path, "HOME": str(home), "MAGICIAN_HOME": str(home / "magician"), "LC_ALL": "C",
            "KG_PARSER": "regex"}


def req(rid, method, params=None) -> dict:
    m = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        m["params"] = params
    return m


def call(rid, name, args=None, modern=False) -> dict:
    p = {"name": name, "arguments": args or {}}
    if modern:
        p["_meta"] = META
    return req(rid, "tools/call", p)


INIT = req(0, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                             "clientInfo": {"name": "test", "version": "1"}})
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class KgMcpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="kg-mcp-"))
        cls.repo = cls.tmp / "repo"
        cls.repo.mkdir()
        for name, body in FILES.items():
            (cls.repo / name).write_text(body, encoding="utf-8")
        cls.env = env_for(cls.tmp)
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q"], cwd=cls.repo, env=cls.env, check=True)
            subprocess.run(["git", "add", "."], cwd=cls.repo, env=cls.env, check=True)
        p = subprocess.run([str(KG), "init"], cwd=cls.repo, env=cls.env, capture_output=True,
                           text=True, timeout=120)
        assert p.returncode == 0, p.stderr
        dbs = list((cls.tmp / "magician" / "knowledge-graph" / "repos").glob("*/graph.db"))
        assert len(dbs) == 1, dbs
        cls.db = dbs[0]
        cls.empty_home = cls.tmp / "empty"
        cls.empty_home.mkdir()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ── helpers
    def session(self, messages, env=None, raw: bytes | None = None, args=()) -> list:
        data = raw if raw is not None else b"".join(
            (m if isinstance(m, bytes) else json.dumps(m).encode()) + b"\n" for m in messages)
        p = subprocess.run([str(SERVER), "--repo", str(self.repo), *args], input=data,
                           capture_output=True, env=env or self.env, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr.decode())
        out = p.stdout.decode("utf-8")
        self.assertTrue(out == "" or out.endswith("\n"))
        return [json.loads(line) for line in out.splitlines()]

    def by_id(self, responses) -> dict:
        return {r.get("id"): r for r in responses}

    def tools(self) -> list:
        return self.by_id(self.session([INIT, INITIALIZED, req(1, "tools/list")]))[1]["result"]["tools"]

    def assert_matches_schema(self, value, schema) -> None:
        """Enough of JSON Schema for the server's own output schemas: type, required, properties, items."""
        types = schema.get("type")
        if types is not None:
            types = types if isinstance(types, list) else [types]
            py = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None),
                  "integer": int, "number": (int, float)}
            ok = any(isinstance(value, py[t]) and not (t in ("integer", "number") and isinstance(value, bool))
                     for t in types)
            self.assertTrue(ok, f"{value!r} is not {types}")
        if isinstance(value, dict):
            for key in schema.get("required", []):
                self.assertIn(key, value)
            for key, sub in schema.get("properties", {}).items():
                if key in value:
                    self.assert_matches_schema(value[key], sub)
            self.assertLessEqual(set(value), set(schema.get("properties", {})) or set(value))
        if isinstance(value, list) and "items" in schema:
            for item in value:
                self.assert_matches_schema(item, schema["items"])

    def snapshot(self) -> dict:
        snap = {}
        for base in (self.db.parent, self.repo):
            for p in sorted(base.rglob("*")):
                if p.is_file() and ".git" not in p.parts and not p.name.endswith(("-wal", "-shm")):
                    snap[str(p)] = (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
        return snap

    # ── legacy era
    def test_legacy_handshake_lists_and_calls_tools(self) -> None:
        r = self.by_id(self.session([INIT, INITIALIZED, req(1, "tools/list"), req(2, "ping"),
                                     call(3, "kg_query", {"query": "helper"})]))
        self.assertEqual(sorted(r), [0, 1, 2, 3])          # the notification got no answer
        init = r[0]["result"]
        self.assertEqual(init["protocolVersion"], "2025-11-25")
        self.assertEqual(init["capabilities"], {"tools": {}})
        self.assertEqual(init["serverInfo"]["name"], "magician-kg")
        self.assertIn("kg_query", init["instructions"])
        self.assertNotIn("resultType", init)
        self.assertEqual(r[2]["result"], {})
        res = r[3]["result"]
        self.assertFalse(res["isError"])
        self.assertEqual(res["content"][0]["type"], "text")
        self.assertIn("util.py:1", res["content"][0]["text"])
        schema = next(t for t in r[1]["result"]["tools"] if t["name"] == "kg_query")["outputSchema"]
        self.assert_matches_schema(res["structuredContent"], schema)
        top = res["structuredContent"]["results"][0]
        self.assertEqual((top["path"], top["line"], top["symbol"]), ("util.py", 1, "helper"))
        self.assertLessEqual(set(top), {"path", "line", "end_line", "symbol", "kind", "score", "snippet"})

    def test_legacy_version_negotiation(self) -> None:
        old = req(0, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}})
        r = self.by_id(self.session([old, req(1, "tools/list"), call(2, "kg_query", {"query": "helper"})]))
        self.assertEqual(r[0]["result"]["protocolVersion"], "2025-03-26")
        self.assertTrue(all("outputSchema" not in t for t in r[1]["result"]["tools"]))
        self.assertNotIn("structuredContent", r[2]["result"])   # structured output starts at 2025-06-18
        unknown = req(0, "initialize", {"protocolVersion": "1999-01-01", "capabilities": {}})
        self.assertEqual(self.session([unknown])[0]["result"]["protocolVersion"], "2025-11-25")

    # ── modern era
    def test_modern_discover_and_stateless_calls(self) -> None:
        r = self.by_id(self.session([req(1, "server/discover", {"_meta": META}),
                                     req(2, "tools/list", {"_meta": META}),
                                     call(3, "kg_blast", {"target": "util.py"}, modern=True)]))
        d = r[1]["result"]
        self.assertIn(MODERN, d["supportedVersions"])
        self.assertEqual(d["capabilities"], {"tools": {}})
        self.assertEqual(d["resultType"], "complete")
        self.assertIsInstance(d["ttlMs"], int)
        self.assertIn(d["cacheScope"], ("public", "private"))
        self.assertEqual(d["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "magician-kg")
        self.assertTrue(d["instructions"])
        lst = r[2]["result"]
        self.assertEqual((lst["resultType"], lst["cacheScope"]), ("complete", "public"))
        self.assertEqual([t["name"] for t in lst["tools"]], [t["name"] for t in self.tools()])
        blast = r[3]["result"]
        self.assertEqual(blast["resultType"], "complete")
        self.assertFalse(blast["isError"])
        self.assertEqual([x["path"] for x in blast["structuredContent"]["impacted"]], ["app.py"])

    def test_modern_errors(self) -> None:
        bad_version = dict(META, **{"io.modelcontextprotocol/protocolVersion": "2030-01-01"})
        no_caps = {k: v for k, v in META.items() if k != "io.modelcontextprotocol/clientCapabilities"}
        r = self.by_id(self.session([req(1, "tools/list", {"_meta": bad_version}),
                                     req(2, "tools/list", {"_meta": no_caps}),
                                     req(3, "ping", {"_meta": META}),
                                     req(4, "initialize", {"_meta": META})]))
        self.assertEqual(r[1]["error"]["code"], -32022)
        self.assertEqual(r[1]["error"]["data"], {"supported": [MODERN], "requested": "2030-01-01"})
        self.assertEqual(r[2]["error"]["code"], -32602)
        self.assertEqual(r[3]["error"]["code"], -32601)    # ping was removed in 2026-07-28
        self.assertEqual(r[4]["error"]["code"], -32601)    # so was initialize

    def test_era_is_chosen_per_request(self) -> None:
        """A legacy session on the same pipe does not change how a modern request is served, and a
        server/discover probe without _meta still gets a DiscoverResult."""
        old = req(0, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}})
        r = self.by_id(self.session([old, call(1, "kg_query", {"query": "helper"}, modern=True),
                                     call(2, "kg_query", {"query": "helper"}),
                                     req(3, "server/discover")]))
        self.assertIn("structuredContent", r[1]["result"])
        self.assertEqual(r[1]["result"]["resultType"], "complete")
        self.assertNotIn("structuredContent", r[2]["result"])
        self.assertIn(MODERN, r[3]["result"]["supportedVersions"])

    # ── tool list
    def test_tool_list_is_small_prefixed_and_read_only(self) -> None:
        tools = self.tools()
        names = [t["name"] for t in tools]
        self.assertLessEqual(len(tools), 5)
        self.assertEqual(names, ["kg_query", "kg_blast", "kg_neighbors", "kg_status"])
        for t in tools:
            with self.subTest(tool=t["name"]):
                self.assertRegex(t["name"], r"^kg_[a-z_]+$")
                self.assertTrue(t["description"])
                self.assertEqual(t["inputSchema"]["type"], "object")
                self.assertFalse(t["inputSchema"]["additionalProperties"])
                self.assertEqual(t["outputSchema"]["type"], "object")
                a = t["annotations"]
                self.assertIs(a["readOnlyHint"], True)
                self.assertIs(a["openWorldHint"], False)
                self.assertIs(a["idempotentHint"], True)
                self.assertIs(a["destructiveHint"], False)
                self.assertLess(len(json.dumps(t)), 2048)
        self.assertEqual(tools, self.tools())              # deterministic across processes

    def test_every_tool_result_matches_its_output_schema(self) -> None:
        schemas = {t["name"]: t["outputSchema"] for t in self.tools()}
        calls = {"kg_query": {"query": "parse", "limit": 3}, "kg_blast": {"target": "helper", "depth": 1},
                 "kg_neighbors": {"target": "util.py"}, "kg_status": {}}
        msgs = [INIT] + [call(i, n, a) for i, (n, a) in enumerate(calls.items(), 1)]
        r = self.by_id(self.session(msgs))
        for i, name in enumerate(calls, 1):
            with self.subTest(tool=name):
                res = r[i]["result"]
                self.assertFalse(res["isError"], res["content"])
                self.assert_matches_schema(res["structuredContent"], schemas[name])
                self.assertTrue(res["content"][0]["text"])
        st = r[4]["result"]["structuredContent"]
        self.assertEqual((st["indexed"], st["files"], st["stale"]), (True, 3, 0))

    # ── cursors
    def test_cursor_pagination_round_trips_across_processes(self) -> None:
        full = self.session([INIT, call(1, "kg_query", {"query": "parse", "limit": 100})])[1]
        want = [(x["path"], x["line"]) for x in full["result"]["structuredContent"]["results"]]
        self.assertNotIn("nextCursor", full["result"]["structuredContent"])
        self.assertGreaterEqual(len(want), 5)
        got, cursor, pages = [], None, 0
        while True:
            args = {"query": "parse", "limit": 2}
            if cursor:
                args["cursor"] = cursor
            # a fresh server process for every page: the cursor carries all the state
            res = self.session([INIT, call(1, "kg_query", args)])[1]["result"]
            self.assertFalse(res["isError"], res["content"])
            sc = res["structuredContent"]
            got += [(x["path"], x["line"]) for x in sc["results"]]
            pages += 1
            cursor = sc.get("nextCursor")
            if not cursor:
                break
            self.assertLess(pages, 10)
        self.assertEqual(got, want)
        self.assertEqual(pages, -(-len(want) // 2))

    def test_bad_cursors_are_tool_errors(self) -> None:
        first = self.session([INIT, call(1, "kg_query", {"query": "parse", "limit": 2})])[1]
        cursor = first["result"]["structuredContent"]["nextCursor"]
        r = self.by_id(self.session([INIT, call(1, "kg_query", {"query": "other", "cursor": cursor}),
                                     call(2, "kg_query", {"query": "parse", "cursor": "not-a-cursor"})]))
        for i in (1, 2):
            self.assertTrue(r[i]["result"]["isError"])
            self.assertIn("without a cursor", r[i]["result"]["content"][0]["text"])

    # ── actionable tool errors
    def test_no_index_reports_the_instruction(self) -> None:
        env = env_for(self.empty_home)
        r = self.by_id(self.session([INIT, call(1, "kg_status"), call(2, "kg_query", {"query": "x"}),
                                     call(3, "kg_blast", {"target": "x"})], env=env))
        st = r[1]["result"]
        self.assertTrue(st["isError"])
        self.assertIn("kg init", st["content"][0]["text"])
        self.assertIs(st["structuredContent"]["indexed"], False)
        self.assertIn("kg init", st["structuredContent"]["instruction"])
        for i in (2, 3):
            self.assertTrue(r[i]["result"]["isError"])
            self.assertIn("kg init", r[i]["result"]["content"][0]["text"])
        self.assertFalse((self.empty_home / "magician").exists())   # nothing was created

    def test_bad_arguments_and_unknown_targets_are_tool_errors(self) -> None:
        r = self.by_id(self.session([INIT,
                                     call(1, "kg_query", {"query": "x", "limit": 0}),
                                     call(2, "kg_query", {"query": "x", "extra": 1}),
                                     call(3, "kg_query", {}),
                                     call(4, "kg_blast", {"target": "no_such_symbol_zz"}),
                                     call(5, "kg_neighbors", {"target": "util.py", "depth": "2"}),
                                     call(6, "kg_query", {"query": "zzzzqqq"})]))
        for i, needle in ((1, "1 to 100"), (2, "extra"), (3, "query"), (4, "kg_query"), (5, "integer")):
            with self.subTest(call=i):
                self.assertTrue(r[i]["result"]["isError"])
                self.assertIn(needle, r[i]["result"]["content"][0]["text"])
        self.assertFalse(r[6]["result"]["isError"])                 # no match is not an error
        self.assertEqual(r[6]["result"]["structuredContent"]["results"], [])

    # ── protocol errors
    def test_protocol_faults_are_json_rpc_errors(self) -> None:
        msgs = [b"{not json", INIT, req(1, "no/such/method"), [req(2, "ping")],
                {"jsonrpc": "1.0", "id": 3, "method": "ping"}, call(4, "kg_nope"),
                req(5, "tools/list", {"cursor": "abc"}), {"jsonrpc": "2.0", "method": "unknown/note"},
                {"jsonrpc": "2.0", "id": None, "method": "ping"}, req(6, "ping")]
        out = self.session(msgs)
        self.assertEqual(out[0], {"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32700, "message": out[0]["error"]["message"]}})
        r = self.by_id(out[1:])
        self.assertEqual(r[1]["error"]["code"], -32601)
        self.assertEqual(r[3]["error"]["code"], -32600)
        self.assertEqual(r[4]["error"]["code"], -32602)
        self.assertIn("kg_query", r[4]["error"]["message"])
        self.assertEqual(r[5]["error"]["code"], -32602)
        self.assertEqual(r[6]["result"], {})                         # still serving after the faults
        nulls = [x for x in out[1:] if x.get("id") is None]
        self.assertEqual([x["error"]["code"] for x in nulls], [-32600, -32600])   # batch, null id
        self.assertEqual(len(out), 9)                                # the notification got no answer

    def test_exits_cleanly_on_eof_and_ignores_blank_lines(self) -> None:
        self.assertEqual(self.session([], raw=b""), [])
        self.assertEqual(self.session([], raw=b"\n\n" + json.dumps(req(1, "ping")).encode() + b"\n")[0]["id"], 1)

    # ── read-only
    def test_server_writes_nothing(self) -> None:
        before = self.snapshot()
        self.session([INIT, call(1, "kg_query", {"query": "helper"}), call(2, "kg_blast", {"target": "util.py"}),
                      call(3, "kg_neighbors", {"target": "helper"}), call(4, "kg_status"),
                      call(5, "kg_query", {"query": "parse", "limit": 1}),
                      req(6, "server/discover", {"_meta": META})])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.db.parent / "cache").exists())
        self.assertFalse((ROOT / "tools" / "__pycache__").exists())   # no bytecode in the plugin folder

    def test_database_connection_refuses_writes(self) -> None:
        saved = sys.dont_write_bytecode
        sys.dont_write_bytecode = True                              # no __pycache__ in tools/
        try:
            loader = SourceFileLoader("kg_mcp_under_test", str(SERVER))
            spec = importlib.util.spec_from_loader("kg_mcp_under_test", loader)
            mod = importlib.util.module_from_spec(spec)
            loader.exec_module(mod)
        finally:
            sys.dont_write_bytecode = saved
        cx = mod.ro_connect(str(self.db))
        try:
            self.assertEqual(cx.execute("PRAGMA query_only").fetchone()[0], 1)
            cx.execute("PRAGMA query_only=OFF")                     # mode=ro still refuses
            with self.assertRaises(sqlite3.OperationalError):
                cx.execute("CREATE TABLE intruder(x)")
            with self.assertRaises(sqlite3.OperationalError):
                cx.execute("DELETE FROM nodes")
        finally:
            cx.close()
        src = SERVER.read_text(encoding="utf-8")
        self.assertIn("?mode=ro", src)
        self.assertIn("PRAGMA query_only=ON", src)
        self.assertNotIn("cache_put", src)

    # ── packaging
    def test_tool_file_is_stdlib_executable_and_offline(self) -> None:
        self.assertTrue(os.access(SERVER, os.X_OK))
        src = SERVER.read_text(encoding="utf-8")
        self.assertTrue(src.startswith("#!/usr/bin/env python3\n"))
        imports = {line.split()[1].split(".")[0] for line in src.splitlines()
                   if line.strip().startswith(("import ", "from ")) and not line.startswith("#")}
        self.assertLessEqual(imports, {"base64", "json", "os", "sqlite3", "sys", "time", "importlib", "__future__"})
        p = subprocess.run([str(SERVER), "--version"], capture_output=True, text=True, env=self.env, timeout=30)
        self.assertEqual(p.returncode, 0)
        self.assertTrue(p.stdout.startswith("kg-mcp "))

    def test_plugin_does_not_register_the_server(self) -> None:
        """Registering it would add tool definitions to every session; it stays opt-in."""
        self.assertFalse((ROOT / ".mcp.json").exists())
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertNotIn("mcpServers", manifest)
        doc = (ROOT / "skills" / "knowledge-graph" / "references" / "mcp-server.md").read_text(encoding="utf-8")
        self.assertIn("claude mcp add", doc)
        self.assertIn("mcpServers", doc)


if __name__ == "__main__":
    unittest.main()
