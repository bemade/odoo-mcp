import os
from itertools import count
from typing import Any

import httpx


class OdooAPIError(Exception):
    """Raised when the Odoo API returns an error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Odoo API error {status_code}: {message}")


class OdooClient:
    """Async client for the Odoo 19.0 API.

    Supports two authentication modes:

    * **Bearer** (API key): uses the JSON-2 endpoint
      ``POST /json/2/{model}/{method}`` with an ``Authorization: Bearer``
      header.
    * **Session** (username/password): authenticates via
      ``/web/session/authenticate`` (JSON-RPC) then calls
      ``/web/dataset/call_kw/{model}/{method}`` with the session cookie.

    The mode is chosen automatically based on which credentials are supplied.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        self.base_url = (base_url or os.environ["ODOO_URL"]).rstrip("/")
        self.api_key = api_key or os.environ.get("ODOO_API_KEY")
        self.username = username or os.environ.get("ODOO_USERNAME")
        self.password = password or os.environ.get("ODOO_PASSWORD")
        self.database = database or os.environ.get("ODOO_DB")

        if self.api_key:
            self._use_bearer = True
        elif self.username and self.password:
            self._use_bearer = False
            if not self.database:
                raise ValueError(
                    "ODOO_DB is required when using username/password authentication"
                )
        else:
            raise ValueError(
                "Provide either ODOO_API_KEY or both ODOO_USERNAME and ODOO_PASSWORD"
            )

        self._client: httpx.AsyncClient | None = None
        self._authenticated = False
        self._jsonrpc_id = count(1)

    # -- HTTP client lifecycle -----------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._use_bearer:
                headers["Authorization"] = f"Bearer {self.api_key}"
                if self.database:
                    headers["X-Odoo-Database"] = self.database
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0,
            )
        if not self._use_bearer and not self._authenticated:
            await self._authenticate_session()
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -- Session authentication ----------------------------------------------

    async def _authenticate_session(self) -> None:
        """Authenticate with username/password via JSON-RPC."""
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": next(self._jsonrpc_id),
            "params": {
                "db": self.database,
                "login": self.username,
                "password": self.password,
            },
        }
        response = await self._client.post(
            "/web/session/authenticate", json=payload
        )
        if response.status_code >= 400:
            raise OdooAPIError(response.status_code, response.text)

        data = response.json()
        if "error" in data:
            msg = _extract_jsonrpc_error(data)
            raise OdooAPIError(401, msg)

        uid = (data.get("result") or {}).get("uid")
        if not uid:
            raise OdooAPIError(401, "Authentication failed: invalid credentials")

        self._authenticated = True

    # -- Method dispatch -----------------------------------------------------

    async def execute(
        self,
        model: str,
        method: str,
        ids: list[int] | None = None,
        context: dict | None = None,
        **kwargs,
    ) -> Any:
        """Call any public method on an Odoo model.

        Dispatches to the JSON-2 or JSON-RPC transport depending on the
        authentication mode.
        """
        if self._use_bearer:
            return await self._execute_json2(
                model, method, ids, context, **kwargs
            )
        return await self._execute_jsonrpc(
            model, method, ids, context, **kwargs
        )

    # -- JSON-2 transport (Bearer) -------------------------------------------

    async def _execute_json2(
        self,
        model: str,
        method: str,
        ids: list[int] | None,
        context: dict | None,
        **kwargs,
    ) -> Any:
        """POST /json/2/{model}/{method} with flat named parameters."""
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
                message = detail.get("message") or detail.get(
                    "error", response.text
                )
            except Exception:
                message = response.text
            raise OdooAPIError(response.status_code, message)

        return response.json()

    # -- JSON-RPC transport (Session) ----------------------------------------

    async def _execute_jsonrpc(
        self,
        model: str,
        method: str,
        ids: list[int] | None,
        context: dict | None,
        **kwargs,
    ) -> Any:
        """POST /web/dataset/call_kw/{model}/{method} with JSON-RPC envelope."""
        client = await self._get_client()

        kw = dict(kwargs)
        if context is not None:
            kw["context"] = context

        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "id": next(self._jsonrpc_id),
            "params": {
                "model": model,
                "method": method,
                "args": [ids] if ids is not None else [],
                "kwargs": kw,
            },
        }

        response = await client.post(
            f"/web/dataset/call_kw/{model}/{method}", json=payload
        )

        if response.status_code >= 400:
            try:
                detail = response.json()
                message = detail.get("message") or detail.get(
                    "error", response.text
                )
            except Exception:
                message = response.text
            raise OdooAPIError(response.status_code, message)

        data = response.json()
        if "error" in data:
            raise OdooAPIError(200, _extract_jsonrpc_error(data))

        return data.get("result")

    # -- Convenience methods -------------------------------------------------

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

    async def create(self, model: str, values: dict) -> int:
        """Create a new record and return its ID."""
        return await self.execute(model, "create", vals_list=values)

    async def write(self, model: str, ids: list[int], values: dict) -> bool:
        """Update existing records with the given values."""
        return await self.execute(model, "write", ids=ids, vals=values)

    async def unlink(self, model: str, ids: list[int]) -> bool:
        """Delete records by ID."""
        return await self.execute(model, "unlink", ids=ids)

    # -- Documentation endpoints ---------------------------------------------

    async def _request(self, path: str) -> Any:
        """POST to an arbitrary path with an empty JSON body."""
        client = await self._get_client()
        response = await client.post(path, json={})
        if response.status_code >= 400:
            try:
                detail = response.json()
                message = detail.get("message") or detail.get(
                    "error", response.text
                )
            except Exception:
                message = response.text
            raise OdooAPIError(response.status_code, message)
        return response.json()

    @property
    def _doc_prefix(self) -> str:
        return "/doc-bearer" if self._use_bearer else "/doc"

    async def get_doc_index(self) -> dict:
        """Fetch the documentation index."""
        return await self._request(f"{self._doc_prefix}/index.json")

    async def get_doc(self, model: str) -> dict:
        """Fetch full field and method documentation for a single model."""
        return await self._request(f"{self._doc_prefix}/{model}.json")


def _extract_jsonrpc_error(data: dict) -> str:
    """Pull a human-readable message from a JSON-RPC error response."""
    error = data["error"]
    return (
        error.get("data", {}).get("message")
        or error.get("message")
        or str(error)
    )
