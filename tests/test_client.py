import json

import httpx
import pytest

from odoo_mcp.client import OdooAPIError, OdooClient


@pytest.fixture
def client():
    return OdooClient(
        base_url="https://odoo.example.com",
        api_key="test-api-key",
        database="testdb",
    )


@pytest.fixture
def mock_transport():
    """Create an httpx mock transport that records requests."""
    requests = []
    response_data: dict | list = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(handler)
    return transport, requests, lambda data: response_data.__class__.__init__(
        response_data, data
    )


class TestOdooClientInit:
    def test_strips_trailing_slash(self):
        client = OdooClient(
            base_url="https://odoo.example.com/",
            api_key="key",
        )
        assert client.base_url == "https://odoo.example.com"

    def test_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "https://env.example.com")
        monkeypatch.setenv("ODOO_API_KEY", "env-key")
        monkeypatch.setenv("ODOO_DB", "env-db")
        client = OdooClient()
        assert client.base_url == "https://env.example.com"
        assert client.api_key == "env-key"
        assert client.database == "env-db"

    def test_database_optional(self, monkeypatch):
        monkeypatch.delenv("ODOO_DB", raising=False)
        client = OdooClient(
            base_url="https://odoo.example.com",
            api_key="key",
        )
        assert client.database is None


class TestExecute:
    @pytest.mark.asyncio
    async def test_posts_to_correct_endpoint(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"result": "ok"})

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        await client.execute("res.partner", "search_read", domain=[])

        assert len(requests) == 1
        assert requests[0].url.path == "/json/2/res.partner/search_read"
        body = json.loads(requests[0].content)
        assert body == {"domain": []}

    @pytest.mark.asyncio
    async def test_includes_ids_and_context(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=[{"id": 1}])

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        await client.execute(
            "res.partner", "read", ids=[1, 2], context={"lang": "fr_FR"}
        )

        body = json.loads(requests[0].content)
        assert body["ids"] == [1, 2]
        assert body["context"] == {"lang": "fr_FR"}

    @pytest.mark.asyncio
    async def test_raises_on_error_response(self, client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403, json={"message": "Access Denied"}
            )

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        with pytest.raises(OdooAPIError) as exc_info:
            await client.execute("res.partner", "read", ids=[1])

        assert exc_info.value.status_code == 403
        assert "Access Denied" in exc_info.value.message


class TestConvenienceMethods:
    @pytest.mark.asyncio
    async def test_search_read_passes_params(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=[])

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        await client.search_read(
            "res.partner",
            domain=[["is_company", "=", True]],
            fields=["name", "email"],
            limit=10,
            offset=5,
            order="name asc",
        )

        body = json.loads(requests[0].content)
        assert body["domain"] == [["is_company", "=", True]]
        assert body["fields"] == ["name", "email"]
        assert body["limit"] == 10
        assert body["offset"] == 5
        assert body["order"] == "name asc"

    @pytest.mark.asyncio
    async def test_search_read_omits_none_params(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=[])

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        await client.search_read("res.partner")

        body = json.loads(requests[0].content)
        assert body == {}

    @pytest.mark.asyncio
    async def test_read_passes_fields(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=[{"id": 1, "name": "Test"}])

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        await client.read("res.partner", [1], fields=["name"])

        body = json.loads(requests[0].content)
        assert body["ids"] == [1]
        assert body["fields"] == ["name"]

    @pytest.mark.asyncio
    async def test_fields_get(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"name": {"type": "char"}})

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        result = await client.fields_get(
            "res.partner", attributes=["type", "string"]
        )

        body = json.loads(requests[0].content)
        assert body["attributes"] == ["type", "string"]
        assert result == {"name": {"type": "char"}}

    @pytest.mark.asyncio
    async def test_search(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=[1, 2, 3])

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        result = await client.search(
            "res.partner", domain=[["is_company", "=", True]], limit=3
        )

        assert result == [1, 2, 3]
        body = json.loads(requests[0].content)
        assert body["domain"] == [["is_company", "=", True]]
        assert body["limit"] == 3


class TestWriteMethods:
    @pytest.mark.asyncio
    async def test_create_posts_values_and_returns_id(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=42)

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        result = await client.create("res.partner", {"name": "Acme"})

        assert result == 42
        assert requests[0].url.path == "/json/2/res.partner/create"
        body = json.loads(requests[0].content)
        assert body == {"vals_list": {"name": "Acme"}}

    @pytest.mark.asyncio
    async def test_write_posts_ids_and_values(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=True)

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        result = await client.write("res.partner", [1, 2], {"name": "Updated"})

        assert result is True
        assert requests[0].url.path == "/json/2/res.partner/write"
        body = json.loads(requests[0].content)
        assert body == {"ids": [1, 2], "vals": {"name": "Updated"}}

    @pytest.mark.asyncio
    async def test_unlink_posts_ids(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=True)

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        result = await client.unlink("res.partner", [1, 2])

        assert result is True
        assert requests[0].url.path == "/json/2/res.partner/unlink"
        body = json.loads(requests[0].content)
        assert body == {"ids": [1, 2]}


class TestDocMethods:
    @pytest.mark.asyncio
    async def test_get_doc_index_posts_to_correct_endpoint(self, client):
        requests = []
        index_data = {"modules": ["base"], "models": []}

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=index_data)

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        result = await client.get_doc_index()

        assert result == index_data
        assert requests[0].url.path == "/doc-bearer/index.json"
        body = json.loads(requests[0].content)
        assert body == {}

    @pytest.mark.asyncio
    async def test_get_doc_posts_model_name_in_url(self, client):
        requests = []
        doc_data = {
            "model": "res.partner",
            "name": "Contact",
            "fields": {},
            "methods": {"write": {"signature": "(values)"}},
        }

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=doc_data)

        client._client = httpx.AsyncClient(
            base_url=client.base_url,
            transport=httpx.MockTransport(handler),
        )

        result = await client.get_doc("res.partner")

        assert result == doc_data
        assert requests[0].url.path == "/doc-bearer/res.partner.json"
        body = json.loads(requests[0].content)
        assert body == {}
