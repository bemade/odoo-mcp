from mcp.server.fastmcp import FastMCP

from odoo_mcp.client import OdooClient

mcp = FastMCP("odoo")

_client: OdooClient | None = None


def _get_client() -> OdooClient:
    global _client
    if _client is None:
        _client = OdooClient()
    return _client


@mcp.tool()
async def search_records(
    model: str,
    domain: list | None = None,
    fields: list[str] | None = None,
    limit: int = 80,
    offset: int = 0,
    order: str | None = None,
) -> list[dict]:
    """Search for records in any Odoo model.

    Args:
        model: The Odoo model name (e.g. "res.partner", "sale.order").
        domain: Odoo domain filter (e.g. [["is_company", "=", true]]).
            Defaults to [] (all records).
        fields: List of field names to return. Defaults to all fields.
        limit: Maximum number of records to return. Defaults to 80.
        offset: Number of records to skip (for pagination).
        order: Sort order (e.g. "name asc, id desc").
    """
    client = _get_client()
    return await client.search_read(
        model,
        domain=domain,
        fields=fields,
        limit=limit,
        offset=offset,
        order=order,
    )


@mcp.tool()
async def read_record(
    model: str,
    ids: list[int],
    fields: list[str] | None = None,
) -> list[dict]:
    """Read specific Odoo records by their IDs.

    Args:
        model: The Odoo model name (e.g. "res.partner").
        ids: List of record IDs to read.
        fields: List of field names to return. Defaults to all fields.
    """
    client = _get_client()
    return await client.read(model, ids, fields=fields)


@mcp.tool()
async def list_models(
    domain: list | None = None,
    limit: int = 80,
    offset: int = 0,
) -> list[dict]:
    """List installed Odoo models.

    Args:
        domain: Optional domain filter on ir.model
            (e.g. [["model", "like", "sale"]]).
        limit: Maximum number of models to return. Defaults to 80.
        offset: Number of records to skip (for pagination).
    """
    client = _get_client()
    return await client.search_read(
        "ir.model",
        domain=domain,
        fields=["model", "name", "info"],
        limit=limit,
        offset=offset,
        order="model",
    )


@mcp.tool()
async def get_model_fields(
    model: str,
    attributes: list[str] | None = None,
) -> dict:
    """Get field definitions for an Odoo model.

    Returns a dict mapping field names to their metadata (type, string,
    required, relation, etc.).

    Args:
        model: The Odoo model name (e.g. "res.partner").
        attributes: List of field attributes to return
            (e.g. ["string", "type", "required"]). Defaults to all.
    """
    client = _get_client()
    return await client.fields_get(model, attributes=attributes)


def main():
    mcp.run()
