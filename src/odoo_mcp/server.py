from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from odoo_mcp.client import OdooClient

mcp = FastMCP("odoo")

_client: OdooClient | None = None


def _get_client() -> OdooClient:
    global _client
    if _client is None:
        _client = OdooClient()
    return _client


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
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


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False, idempotentHint=False, openWorldHint=False
    )
)
async def create_record(
    model: str,
    values: dict,
) -> int:
    """Create a new record in an Odoo model.

    Args:
        model: The Odoo model name (e.g. "res.partner").
        values: Dict of field names to values (e.g. {"name": "Acme"}).

    Returns:
        The ID of the newly created record.
    """
    client = _get_client()
    return await client.create(model, values)


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=True, idempotentHint=True, openWorldHint=False
    )
)
async def update_records(
    model: str,
    ids: list[int],
    values: dict,
) -> bool:
    """Update existing records in an Odoo model.

    Args:
        model: The Odoo model name (e.g. "res.partner").
        ids: List of record IDs to update.
        values: Dict of field names to new values.

    Returns:
        True if the update succeeded.
    """
    client = _get_client()
    return await client.write(model, ids, values)


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=True, idempotentHint=False, openWorldHint=False
    )
)
async def delete_records(
    model: str,
    ids: list[int],
) -> bool:
    """Delete records from an Odoo model.

    Args:
        model: The Odoo model name (e.g. "res.partner").
        ids: List of record IDs to delete.

    Returns:
        True if the deletion succeeded.
    """
    client = _get_client()
    return await client.unlink(model, ids)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
async def get_model_doc(model: str, method: str | None = None) -> dict:
    """Get API documentation for an Odoo model.

    Without a method name, returns a compact summary: each method's name and
    call signature.  With a method name, returns that method's full
    documentation (parameters, types, defaults, docstring, return type).

    Use this before call_method to discover exact parameter names and types.
    Requires the API key user to be in the api_doc.group_allow_doc group.

    Args:
        model: The Odoo model name (e.g. "res.partner").
        method: Optional method name. If provided, returns full docs for that
            method only. If omitted, returns a summary of all methods.
    """
    client = _get_client()
    doc = await client.get_doc(model)
    methods = doc.get("methods", {})
    if method:
        return {method: methods.get(method, f"Method '{method}' not found")}
    return {name: info.get("signature", "") for name, info in methods.items()}


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=True, idempotentHint=False, openWorldHint=False
    )
)
async def call_method(
    model: str,
    method: str,
    ids: list[int] | None = None,
    params: dict | None = None,
) -> Any:
    """Call any public method on an Odoo model.

    Use get_model_doc first to discover the correct parameter names and types.

    Args:
        model: The Odoo model name (e.g. "sale.order").
        method: The method name (e.g. "action_confirm").
        ids: Optional list of record IDs to operate on.
        params: Optional dict of keyword arguments passed to the method.
    """
    client = _get_client()
    return await client.execute(model, method, ids=ids, **(params or {}))


def main():
    mcp.run()
