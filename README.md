# bemade-odoo-mcp

An [MCP](https://modelcontextprotocol.io/) server that connects to Odoo 19.0 via the
JSON-2 API (`/json/2/`), giving AI assistants read access to any Odoo model.

## Features

- **search_records** — Search any model with domain filters, field selection, and pagination
- **read_record** — Read specific records by ID
- **list_models** — List installed Odoo models
- **get_model_fields** — Inspect a model's field schema

## Requirements

- Python 3.12+
- An Odoo 19.0 instance with an API key

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

Set environment variables (or create a `.env` file):

```
ODOO_URL=https://your-odoo-instance.com
ODOO_API_KEY=your-api-key-here
ODOO_DB=your-database-name  # only needed for multi-database setups
```

To create an API key in Odoo, go to **Settings > Users > [your user] > Preferences >
API Keys**.

## Usage with Claude Code

Add to your Claude Code MCP config (`.claude/settings.json`):

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

## Development

```bash
uv sync
uv run pytest
```

## License

LGPL-3.0-only
