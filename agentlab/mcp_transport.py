"""Optional real stdio MCP client. Local mode has no third-party dependencies."""
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from .core import ToolBackend, documents

class MCPBackend:
    def __init__(self, session, names, discovery_ms):
        self.session, self.names, self.discovery_ms = session, names, discovery_ms

    async def call(self, name, args):
        result = await self.session.call_tool(name, args)
        if getattr(result, 'structuredContent', None):
            return result.structuredContent
        text = '\n'.join(x.text for x in result.content if hasattr(x, 'text'))
        try:
            value = json.loads(text)
        except ValueError:
            value = {'text': text}
        if result.isError:
            value['isError'] = True
        return value

@asynccontextmanager
async def backend_context(transport, variant, docs_dir):
    if transport == 'local':
        yield ToolBackend(documents(docs_dir))
        return
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        raise RuntimeError('optional MCP SDK missing: pip install -r requirements-mcp.txt') from None
    params = StdioServerParameters(command=sys.executable, args=['-m', 'agentlab.mcp_server'], env={**os.environ, 'AGENTLAB_VARIANT': variant, 'AGENTLAB_DOCS': str(docs_dir or '')})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            before = time.perf_counter()
            listing = await session.list_tools()
            yield MCPBackend(session, [x.name for x in listing.tools], (time.perf_counter()-before)*1000)
