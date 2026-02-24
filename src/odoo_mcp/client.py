import os
from typing import Any

import httpx


class OdooAPIError(Exception):
    """Raised when the Odoo JSON-2 API returns an error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Odoo API error {status_code}: {message}")


class OdooClient:
    """Async client for the Odoo 19.0 JSON-2 API.

    The JSON-2 API uses ``POST /json/2/{model}/{method}`` with Bearer token
    authentication and named parameters in the JSON body.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        database: str | None = None,
    ):
        self.base_url = (base_url or os.environ["ODOO_URL"]).rstrip("/")
        self.api_key = api_key or os.environ["ODOO_API_KEY"]
        self.database = database or os.environ.get("ODOO_DB")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            if self.database:
                headers["X-Odoo-Database"] = self.database
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def execute(
        self,
        model: str,
        method: str,
        ids: list[int] | None = None,
        context: dict | None = None,
        **kwargs,
    ) -> Any:
        """Call any public method on an Odoo model via the JSON-2 API.

        POST /json/2/{model}/{method}
        Body: {"ids": [...], "context": {...}, **kwargs}
        """
        client = await self._get_client()

        body: dict = {}
        if ids is not None:
            body["ids"] = ids
        if context is not None:
            body["context"] = context
        body.update(kwargs)

        response = await client.post(f"/json/2/{model}/{method}", json=body)

        if response.status_code >= 400:
            try:
                detail = response.json()
                message = detail.get("message") or detail.get("error", response.text)
            except Exception:
                message = response.text
            raise OdooAPIError(response.status_code, message)

        return response.json()

    async def search_read(
        self,
        model: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict]:
        """Search for records and return field values."""
        kwargs: dict = {}
        if domain is not None:
            kwargs["domain"] = domain
        if fields is not None:
            kwargs["fields"] = fields
        if limit is not None:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order is not None:
            kwargs["order"] = order
        return await self.execute(model, "search_read", **kwargs)

    async def read(
        self,
        model: str,
        ids: list[int],
        fields: list[str] | None = None,
    ) -> list[dict]:
        """Read specific records by ID."""
        kwargs: dict = {}
        if fields is not None:
            kwargs["fields"] = fields
        return await self.execute(model, "read", ids=ids, **kwargs)

    async def fields_get(
        self,
        model: str,
        attributes: list[str] | None = None,
    ) -> dict:
        """Get field definitions for a model."""
        kwargs: dict = {}
        if attributes is not None:
            kwargs["attributes"] = attributes
        return await self.execute(model, "fields_get", **kwargs)

    async def search(
        self,
        model: str,
        domain: list | None = None,
        limit: int | None = None,
        offset: int = 0,
        order: str | None = None,
    ) -> list[int]:
        """Search for record IDs matching a domain."""
        kwargs: dict = {}
        if domain is not None:
            kwargs["domain"] = domain
        if limit is not None:
            kwargs["limit"] = limit
        if offset:
            kwargs["offset"] = offset
        if order is not None:
            kwargs["order"] = order
        return await self.execute(model, "search", **kwargs)
