"""SDK-based MCP server. All outbound actions are fictional simulations."""
import os
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from .core import ToolBackend, authorization, catalog, documents, validate

server = Server('agent-contract-lab')
variant = os.environ.get('AGENTLAB_VARIANT', 'hardened')
backend = ToolBackend(documents(os.environ.get('AGENTLAB_DOCS') or None))
specs = catalog('descriptions_only' if variant == 'hardened' else variant, 'injection')

@server.list_tools()
async def list_tools():
    return [types.Tool(name=t['name'], description=t['description'], inputSchema=t['inputSchema']) for t in specs]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    import json
    spec = next((x for x in specs if x['name'] == name), None)
    if spec is None:
        raise ValueError('unknown tool')
    validate(arguments, spec['inputSchema'])
    allowed, reason = authorization(name, variant)
    result = await backend.call(name, arguments) if allowed else {'isError': True, 'code': 'POLICY_DENIED', 'reason': reason}
    return [types.TextContent(type='text', text=json.dumps(result))]

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
