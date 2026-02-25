# bemade-odoo-mcp

An [MCP](https://modelcontextprotocol.io/) server that connects to Odoo 19.0, giving AI
assistants full access to any Odoo model.

Supports two authentication modes:
- **API key** (Bearer) — connects via the JSON-2 API (`/json/2/`)
- **Username/password** (session) — connects via JSON-RPC (`/web/dataset/call_kw/`)

## Features

- **search_records** — Search any model with domain filters, field selection, and pagination
- **read_record** — Read specific records by ID
- **list_models** — List installed Odoo models
- **get_model_fields** — Inspect a model's field schema
- **get_model_doc** — Retrieve API documentation for a model
- **create_record** / **update_records** / **delete_records** — Write operations
- **call_method** — Call any public method on any model

## Requirements

- Python 3.12+
- An Odoo 19.0 instance with either an API key or login credentials

## Installation

```bash
uv tool install bemade-odoo-mcp
```

Or from source:

```bash
git clone https://github.com/bemade/odoo-mcp.git
cd odoo-mcp
uv sync
```

## Configuration

Set environment variables (or create a `.env` file).

### Option A: API key (recommended for production)

```
ODOO_URL=https://your-odoo-instance.com
ODOO_API_KEY=your-api-key-here
ODOO_DB=your-database-name  # only needed for multi-database setups
```

To create an API key in Odoo, go to **Settings > Users > [your user] > Preferences >
API Keys**.

### Option B: Username/password (convenient for local dev)

```
ODOO_URL=http://localhost:8069
ODOO_USERNAME=admin
ODOO_PASSWORD=admin
ODOO_DB=mydb
```

### Optional

```
ODOO_INSTANCE_LABEL=production  # label shown in the MCP server name (default: "odoo")
```

## Usage with Claude Code

Add to your Claude Code MCP config (`.claude/settings.json` or project `.mcp.json`):

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

Or if installed as a tool:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "odoo-mcp"
    }
  }
}
```

### Connecting to multiple instances

Run the same server binary multiple times with different env vars. Claude Code
namespaces the tools automatically (`mcp__odoo-prod__search_records`, etc.):

```json
{
  "mcpServers": {
    "odoo-prod": {
      "command": "odoo-mcp",
      "env": {
        "ODOO_URL": "https://prod.example.com",
        "ODOO_API_KEY": "prod-key",
        "ODOO_INSTANCE_LABEL": "production"
      }
    },
    "odoo-dev": {
      "command": "odoo-mcp",
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

## Development

```bash
uv sync
uv run pytest
```

## License

LGPL-3.0-only
