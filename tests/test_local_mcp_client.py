"""Real subprocess MCP stdio protocol tests with a local fake server.

No GitHub API tokens, no remote calls, no paid tools and no installed MCP
server required for regression. Protocol interactions happen via real pipes.
"""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from asterion_remote.local_mcp_client import McpServerConfig,McpStdioClient


_FAKE = r'''
import json,sys
era=sys.argv[1]
for line in sys.stdin:
    try:
        item=json.loads(line)
        method=item.get("method","")
        ident=item.get("id")
        args=item.get("params",{})
        if ident is None:
            continue
        if era=="modern":
            meta=args.get("_meta",{})
            if meta.get("io.modelcontextprotocol/protocolVersion")!="2026-07-28":
                result={"error":{"code":-32022,"message":"bad protocol"}}
            elif "io.modelcontextprotocol/clientCapabilities" not in meta:
                result={"error":{"code":-32021,"message":"no capabilities"}}
            elif method=="server/discover":
                result={"result":{"resultType":"complete",
                        "supportedVersions":["2026-07-28"],"capabilities":{"tools":{}}}}
            elif method=="tools/list":
                result={"result":{"resultType":"complete","tools":[
                    {"name":"safe.echo","description":"Echo","inputSchema":{"type":"object"}},
                    {"name":"safe.ask","description":"Ask","inputSchema":{"type":"object"}},
                    {"name":"danger.delete","description":"Danger","inputSchema":{"type":"object"}}
                ]}}
            elif method=="tools/call":
                tool=args.get("name")
                if tool=="safe.echo":
                    out=args.get("arguments",{}).get("text","")
                    result={"result":{"resultType":"complete","isError":False,
                            "content":[{"type":"text","text":out}]}}
                elif tool=="safe.ask":
                    result={"result":{"resultType":"input_required","inputRequests":{}}}
                else:
                    result={"result":{"resultType":"complete","isError":True}}
            else:
                result={"error":{"code":-32601,"message":"unknown"}}
        elif method=="initialize":
            result={"result":{"protocolVersion":"2025-11-25",
                    "capabilities":{"tools":{}},"serverInfo":{"name":"fake","version":"1"}}}
        elif method=="tools/list":
            result={"result":{"tools":[
                {"name":"safe.echo","description":"Echo","inputSchema":{"type":"object"}},
                {"name":"danger.delete","description":"Danger","inputSchema":{"type":"object"}}
            ]}}
        elif method=="tools/call":
            tool=args.get("name")
            result={"result":{"isError":tool!="safe.echo",
                    "content":[{"type":"text","text":args.get("arguments",{}).get("text","")}]
            }}
        else:
            result={"error":{"code":-32601,"message":"unknown"}}
        print(json.dumps({"jsonrpc":"2.0","id":ident,**result},separators=(",",":")),
              flush=True)
    except Exception:
        break
'''


class McpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.script=Path(self.tmp.name)/"fake_mcp.py"
        self.script.write_text(_FAKE,encoding="utf-8")
        with open(sys.executable,"rb") as stream:
            self.binary_sha=hashlib.file_digest(stream,"sha256").hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def config(self,era="legacy",**overrides):
        params={
            "executable":Path(sys.executable),
            "sha256":self.binary_sha,
            "arguments":("-u",str(self.script),era),
            "tools_allowed":frozenset({"safe.echo","safe.ask"}),
            "timeout_s":5,
            "protocol":"2026-07-28" if era=="modern" else "2025-11-25"
        }
        params.update(overrides)
        return McpServerConfig(**params)

    def test_bad_binary_sha_and_no_owner_approval_denied(self):
        with self.assertRaises(ValueError):
            self.config(sha256="0"*64)
        with self.assertRaises(ValueError):
            self.config(tools_allowed=frozenset())
        with self.assertRaises(ValueError):
            self.config(arguments=("../bad", "\0"))

    def test_legacy_real_subprocess_and_explicit_tool_allowlist(self):
        with McpStdioClient(self.config()) as client:
            listed=client.list_tools()
            self.assertEqual(listed["owner_authorized_tools"],1)
            self.assertEqual(listed["items"][0]["name"],"safe.echo")
            with self.assertRaises(PermissionError):
                client.call_tool("danger.delete",{"path":"important-file"})
            result=client.call_tool("safe.echo",{"text":"real MCP request"})
            self.assertTrue(result["ok"])
            self.assertEqual(result["result"]["content"][0]["text"],"real MCP request")
            self.assertFalse(result["project_work_verified"])

    def test_modern_2026_discovery_and_tool_call(self):
        with McpStdioClient(self.config("modern")) as client:
            listed=client.list_tools()
            self.assertEqual(listed["owner_authorized_tools"],2)
            result=client.call_tool("safe.echo",{"text":"modern call"})
            self.assertTrue(result["ok"])
            self.assertEqual(result["result"]["content"][0]["text"],"modern call")

    def test_modern_input_required_is_not_false_success(self):
        # Modern MCP can return a partial response requiring owner input.
        # That is NOT a successful tool execution and is not auto-completed.
        with McpStdioClient(self.config("modern")) as client:
            client.list_tools()
            result=client.call_tool("safe.ask",{})
            self.assertFalse(result["ok"])
            self.assertTrue(result["input_required"])
            self.assertFalse(result["project_work_verified"])

    def test_tool_must_be_discovered_and_auth_scoped(self):
        with McpStdioClient(self.config()) as client:
            with self.assertRaises(RuntimeError):
                client.call_tool("safe.echo",{})
            with self.assertRaises(PermissionError):
                client.call_tool("danger.delete",{})

    def test_protocol_does_not_echo_environment_secrets(self):
        with McpStdioClient(self.config(
            inherited_env={"ASTERION_TEST_MCP_SECRET":"opaque-test-secret-123"})) as client:
            listed=client.list_tools()
            self.assertNotIn("opaque-test-secret-123",str(listed))
            result=client.call_tool("safe.echo",{"text":"hello"})
            self.assertNotIn("opaque-test-secret-123",str(result))


if __name__=="__main__":
    unittest.main()
