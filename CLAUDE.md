# odoo-mcp

MCP server that connects to Odoo 19.0 via the JSON-2 API.

## Quick reference

- Run server: `uv run odoo-mcp`
- Run tests: `uv run pytest`
- Add dependency: `uv add <package>`

## Architecture

```
src/odoo_mcp/
├── client.py   # OdooClient — async wrapper around /json/2/{model}/{method}
├── server.py   # FastMCP instance + tool definitions
└── __main__.py # python -m odoo_mcp entry point
```

**Core pattern:** `OdooClient.execute(model, method, **kwargs)` can call any public
Odoo method. Each MCP tool is a thin wrapper that calls a convenience method on the
client.

## Odoo JSON-2 API

- Endpoint: `POST /json/2/{model}/{method}`
- Auth: `Authorization: Bearer <api_key>`
- Multi-db: `X-Odoo-Database: <db>` header
- Body: JSON object with named parameters (`ids`, `domain`, `fields`, etc.)
- Returns: raw JSON result on 200, error object on 4xx/5xx with proper HTTP status codes

## Adding a new tool

1. Add a convenience method to `OdooClient` in `client.py` (optional — can use
   `execute()` directly).
2. Add a `@mcp.tool()` function in `server.py` with type hints and a docstring.
3. Add tests in `tests/`.

## Configuration

Environment variables (or `.env` file):
- `ODOO_URL` — Base URL of the Odoo instance (required)
- `ODOO_API_KEY` — API key for Bearer auth (required)
- `ODOO_DB` — Database name (only needed for multi-db setups)

## Claude Code integration

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/odoo-mcp", "odoo-mcp"]
    }
  }
}
```
