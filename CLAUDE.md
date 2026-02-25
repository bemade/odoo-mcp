# odoo-mcp

MCP server that connects to Odoo 19.0 via the JSON-2 API (Bearer auth) or
JSON-RPC (session auth).

## Quick reference

- Run server: `uv run odoo-mcp`
- Run tests: `uv run pytest`
- Add dependency: `uv add <package>`

## Architecture

```
src/odoo_mcp/
├── client.py   # OdooClient — dual-transport async Odoo client
├── server.py   # FastMCP instance + tool definitions
└── __main__.py # python -m odoo_mcp entry point
```

**Core pattern:** `OdooClient.execute(model, method, **kwargs)` can call any public
Odoo method. Each MCP tool is a thin wrapper that calls a convenience method on the
client.

## Odoo transports

The client auto-selects the transport based on which credentials are provided:

### Bearer (API key) — JSON-2

- Endpoint: `POST /json/2/{model}/{method}`
- Auth: `Authorization: Bearer <api_key>`
- Multi-db: `X-Odoo-Database: <db>` header
- Body: JSON object with named parameters (`ids`, `domain`, `fields`, etc.)
- Returns: raw JSON result on 200, error object on 4xx/5xx

### Session (username/password) — JSON-RPC

- Login: `POST /web/session/authenticate` (JSON-RPC envelope)
- Calls: `POST /web/dataset/call_kw/{model}/{method}` (JSON-RPC envelope)
- Auth: session cookie set after login
- Body: `{"jsonrpc": "2.0", "method": "call", "id": N, "params": {...}}`

## Adding a new tool

1. Add a convenience method to `OdooClient` in `client.py` (optional — can use
   `execute()` directly).
2. Add a `@mcp.tool()` function in `server.py` with type hints and a docstring.
3. Add tests in `tests/`.

## Configuration

Environment variables (or `.env` file):
- `ODOO_URL` — Base URL of the Odoo instance (required)
- `ODOO_API_KEY` — API key for Bearer auth (option A)
- `ODOO_USERNAME` — Login for session auth (option B)
- `ODOO_PASSWORD` — Password for session auth (option B)
- `ODOO_DB` — Database name (required for session auth, optional for Bearer)
- `ODOO_INSTANCE_LABEL` — Human label used in the MCP server name (default: "odoo")

Provide **either** `ODOO_API_KEY` **or** both `ODOO_USERNAME` + `ODOO_PASSWORD`.

## Claude Code integration

Single instance:

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

Multiple instances (env vars inline):

```json
{
  "mcpServers": {
    "odoo-production": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/odoo-mcp", "odoo-mcp"],
      "env": {
        "ODOO_URL": "https://prod.example.com",
        "ODOO_API_KEY": "prod-key",
        "ODOO_INSTANCE_LABEL": "production"
      }
    },
    "odoo-dev": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/odoo-mcp", "odoo-mcp"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_USERNAME": "admin",
        "ODOO_PASSWORD": "admin",
        "ODOO_DB": "mydb",
        "ODOO_INSTANCE_LABEL": "local-dev"
      }
    }
  }
}
```
