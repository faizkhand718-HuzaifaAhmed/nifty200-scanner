"""
Low-level MCP (Model Context Protocol) client glue: connect to a
streamable-HTTP MCP server, discover its tools, and call one.

Deliberately isolated from any NSE-specific logic - this file only knows
how to speak MCP in general. app/market_data/providers/nse_mcp_provider.py
is where NSE-specific tool selection and response parsing lives, kept
separate so THAT logic can be tested with simulated tool results, without
needing the `mcp` package installed or a live network connection (neither
is available in the sandbox this was built in).

The MCP SDK's client API is async (asyncio-based). This project's existing
provider interfaces (app/market_data/base.py) are synchronous, by design,
and every existing caller (scanner, backtest, indicators pipeline) already
depends on that synchronous contract - changing it would mean touching
every one of those call sites, which violates "do not unnecessarily
rewrite working features." Instead, `run_async` bridges a single async
call into the synchronous interface via asyncio.run(). This is safe in
this codebase specifically because every FastAPI route that reaches this
code is a synchronous `def` (not `async def`), which FastAPI runs in a
worker thread, not on the main event loop - so there is no "asyncio.run()
called from a running event loop" conflict here. If a caller ever needs
to invoke this from an async context, this function would need revisiting.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.market_data.exceptions import ProviderAPIError


@dataclass
class MCPToolInfo:
    name: str
    description: str = ""


@dataclass
class MCPToolResult:
    """The parsed-to-plain-Python result of one tool call. MCP tool
    results are a list of content blocks (usually TextContent carrying a
    JSON string, per the MCP spec) - `data` is that JSON already decoded
    where possible, `raw_text` is the original text as a fallback for
    tools that don't return JSON."""
    raw_text: str
    data: Optional[Any]  # parsed JSON if the content was valid JSON, else None
    is_error: bool = False


async def _list_tools_async(server_url: str, auth_token: Optional[str] = None) -> List[MCPToolInfo]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else None
    async with streamablehttp_client(server_url, headers=headers) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [MCPToolInfo(name=t.name, description=getattr(t, "description", "") or "") for t in result.tools]


async def _call_tool_async(
    server_url: str, tool_name: str, arguments: Dict[str, Any], auth_token: Optional[str] = None
) -> MCPToolResult:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else None
    async with streamablehttp_client(server_url, headers=headers) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            text_parts = [block.text for block in result.content if getattr(block, "type", None) == "text"]
            raw_text = "\n".join(text_parts)

            parsed = None
            try:
                parsed = json.loads(raw_text) if raw_text else None
            except (json.JSONDecodeError, ValueError):
                parsed = None

            return MCPToolResult(raw_text=raw_text, data=parsed, is_error=bool(getattr(result, "isError", False)))


def run_async(coro):
    """Bridges one async MCP call into this codebase's synchronous
    provider interface - see this module's docstring for why that's safe
    here specifically."""
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "cannot be called from a running event loop" in str(exc):
            raise ProviderAPIError(
                "MCP client was invoked from within an already-running asyncio event loop - "
                "this bridging function only supports synchronous callers. See "
                "app/market_data/mcp_client.py's module docstring."
            ) from exc
        raise


def list_tools(server_url: str, auth_token: Optional[str] = None) -> List[MCPToolInfo]:
    try:
        return run_async(_list_tools_async(server_url, auth_token))
    except ProviderAPIError:
        raise
    except Exception as exc:
        raise ProviderAPIError(f"could not list tools from MCP server {server_url}: {exc}") from exc


def call_tool(server_url: str, tool_name: str, arguments: Dict[str, Any], auth_token: Optional[str] = None) -> MCPToolResult:
    try:
        result = run_async(_call_tool_async(server_url, tool_name, arguments, auth_token))
    except ProviderAPIError:
        raise
    except Exception as exc:
        raise ProviderAPIError(f"MCP tool call {tool_name!r} on {server_url} failed: {exc}") from exc

    if result.is_error:
        raise ProviderAPIError(f"MCP tool {tool_name!r} returned an error result: {result.raw_text}")
    return result
