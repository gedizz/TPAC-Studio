"""Real stdio transport test through the official SDK client and server."""

import asyncio
import os
import sys

import pytest


def test_mcp_roundtrip(tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tpac_studio.mcp_server", "--root", str(tmp_path)],
            env=dict(os.environ),
        )
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                listing = await session.list_tools()
                assert {"build_plan", "build_execute", "particle_edit", "model_import"} <= {
                    tool.name for tool in listing.tools
                }
                result = await session.call_tool("examples_load", {})
                assert not result.isError and result.structuredContent["ok"]
                result = await session.call_tool("build_plan", {})
                plan = result.structuredContent["result"]
                built = await session.call_tool(
                    "build_execute", {"output": "mcp.tpac", "plan_id": plan["plan_id"]}
                )
                assert (
                    not built.isError and built.structuredContent["result"]["structurally_verified"]
                )
                error = await session.call_tool("package_inspect", {"path": "../outside.tpac"})
                assert (
                    error.isError
                    and error.structuredContent["error"]["code"] == "PATH_OUTSIDE_ROOT"
                )
                resources = await session.list_resources()
                assert len(resources.resources) == 2
                guide = await session.read_resource("tpac://guide")
                assert guide.contents

    asyncio.run(asyncio.wait_for(exercise(), timeout=30))
