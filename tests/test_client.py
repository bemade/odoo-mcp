import json

import httpx
import pytest

from odoo_mcp.client import OdooAPIError, OdooClient


# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def client():
    """Bearer-auth client."""
    return OdooClient(
        base_url="https://odoo.example.com",
        api_key="test-api-key",
        database="testdb",
    )


@pytest.fixture
def session_client():
    """Session-auth client (not yet authenticated)."""
    return OdooClient(
        base_url="https://odoo.example.com",
        username="admin",
        password="admin",
        database="testdb",
    )


def _mock_client(client, handler):
    """Inject a mock transport into an OdooClient, return it ready to use."""
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        transport=httpx.MockTransport(handler),
    )
    return client


def _mock_session_client(client, handler):
    """Inject a mock transport and mark as authenticated."""
    _mock_client(client, handler)
    client._authenticated = True
    return client


# -- Init tests --------------------------------------------------------------


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
        assert client._use_bearer is True

    def test_database_optional_for_bearer(self, monkeypatch):
        monkeypatch.delenv("ODOO_DB", raising=False)
        client = OdooClient(
            base_url="https://odoo.example.com",
            api_key="key",
        )
        assert client.database is None

    def test_session_auth_from_env(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://localhost:8069")
        monkeypatch.setenv("ODOO_USERNAME", "admin")
        monkeypatch.setenv("ODOO_PASSWORD", "admin")
        monkeypatch.setenv("ODOO_DB", "mydb")
        monkeypatch.delenv("ODOO_API_KEY", raising=False)
        client = OdooClient()
        assert client._use_bearer is False
        assert client.username == "admin"

    def test_api_key_takes_precedence(self):
        client = OdooClient(
            base_url="https://odoo.example.com",
            api_key="key",
            username="admin",
            password="admin",
            database="db",
        )
        assert client._use_bearer is True

    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("ODOO_API_KEY", raising=False)
        monkeypatch.delenv("ODOO_USERNAME", raising=False)
        monkeypatch.delenv("ODOO_PASSWORD", raising=False)
        with pytest.raises(ValueError, match="ODOO_API_KEY"):
            OdooClient(base_url="https://odoo.example.com")

    def test_session_requires_database(self):
        with pytest.raises(ValueError, match="ODOO_DB"):
            OdooClient(
                base_url="https://odoo.example.com",
                username="admin",
                password="admin",
            )


# -- Bearer / JSON-2 transport tests ----------------------------------------


class TestExecuteJson2:
    @pytest.mark.asyncio
    async def test_posts_to_correct_endpoint(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={"result": "ok"})

        _mock_client(client, handler)
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

        _mock_client(client, handler)
        await client.execute(
            "res.partner", "read", ids=[1, 2], context={"lang": "fr_FR"}
        )

        body = json.loads(requests[0].content)
        assert body["ids"] == [1, 2]
        assert body["context"] == {"lang": "fr_FR"}

    @pytest.mark.asyncio
    async def test_raises_on_error_response(self, client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"message": "Access Denied"})

        _mock_client(client, handler)

        with pytest.raises(OdooAPIError) as exc_info:
            await client.execute("res.partner", "read", ids=[1])

        assert exc_info.value.status_code == 403
        assert "Access Denied" in exc_info.value.message


# -- Session authentication tests -------------------------------------------


class TestSessionAuthentication:
    @pytest.mark.asyncio
    async def test_authenticate_sends_jsonrpc(self, session_client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"uid": 2, "username": "admin"},
                },
            )

        _mock_client(session_client, handler)
        await session_client._authenticate_session()

        assert len(requests) == 1
        assert requests[0].url.path == "/web/session/authenticate"
        body = json.loads(requests[0].content)
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "call"
        assert body["params"]["db"] == "testdb"
        assert body["params"]["login"] == "admin"
        assert body["params"]["password"] == "admin"
        assert session_client._authenticated is True

    @pytest.mark.asyncio
    async def test_authenticate_fails_on_bad_credentials(self, session_client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"uid": None},
                },
            )

        _mock_client(session_client, handler)

        with pytest.raises(OdooAPIError) as exc_info:
            await session_client._authenticate_session()

        assert exc_info.value.status_code == 401
        assert "invalid credentials" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_authenticate_fails_on_jsonrpc_error(self, session_client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {
                        "message": "Odoo Server Error",
                        "data": {"message": "Database not found."},
                    },
                },
            )

        _mock_client(session_client, handler)

        with pytest.raises(OdooAPIError) as exc_info:
            await session_client._authenticate_session()

        assert exc_info.value.status_code == 401
        assert "Database not found" in exc_info.value.message


# -- JSON-RPC transport tests -----------------------------------------------


class TestExecuteJsonRpc:
    @pytest.mark.asyncio
    async def test_posts_to_call_kw_endpoint(self, session_client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": []}
            )

        _mock_session_client(session_client, handler)
        await session_client.execute(
            "res.partner", "search_read", domain=[]
        )

        assert len(requests) == 1
        assert (
            requests[0].url.path
            == "/web/dataset/call_kw/res.partner/search_read"
        )

    @pytest.mark.asyncio
    async def test_jsonrpc_envelope_format(self, session_client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": []}
            )

        _mock_session_client(session_client, handler)
        await session_client.execute(
            "res.partner", "search_read", domain=[], fields=["name"]
        )

        body = json.loads(requests[0].content)
        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "call"
        assert body["params"]["model"] == "res.partner"
        assert body["params"]["method"] == "search_read"
        assert body["params"]["args"] == []
        assert body["params"]["kwargs"] == {
            "domain": [],
            "fields": ["name"],
        }

    @pytest.mark.asyncio
    async def test_ids_go_in_args(self, session_client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": 1, "result": [{"id": 1}]},
            )

        _mock_session_client(session_client, handler)
        await session_client.execute(
            "res.partner", "read", ids=[1, 2], fields=["name"]
        )

        body = json.loads(requests[0].content)
        assert body["params"]["args"] == [[1, 2]]
        assert body["params"]["kwargs"] == {"fields": ["name"]}

    @pytest.mark.asyncio
    async def test_context_goes_in_kwargs(self, session_client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200, json={"jsonrpc": "2.0", "id": 1, "result": []}
            )

        _mock_session_client(session_client, handler)
        await session_client.execute(
            "res.partner",
            "search_read",
            context={"lang": "fr_FR"},
            domain=[],
        )

        body = json.loads(requests[0].content)
        assert body["params"]["kwargs"]["context"] == {"lang": "fr_FR"}

    @pytest.mark.asyncio
    async def test_returns_result_value(self, session_client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": [{"id": 1, "name": "Test"}],
                },
            )

        _mock_session_client(session_client, handler)
        result = await session_client.execute("res.partner", "search_read")
        assert result == [{"id": 1, "name": "Test"}]

    @pytest.mark.asyncio
    async def test_raises_on_jsonrpc_error(self, session_client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {
                        "message": "Odoo Server Error",
                        "data": {"message": "Record does not exist"},
                    },
                },
            )

        _mock_session_client(session_client, handler)

        with pytest.raises(OdooAPIError) as exc_info:
            await session_client.execute("res.partner", "read", ids=[999])

        assert exc_info.value.status_code == 200
        assert "Record does not exist" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, session_client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="Internal Server Error")

        _mock_session_client(session_client, handler)

        with pytest.raises(OdooAPIError) as exc_info:
            await session_client.execute("res.partner", "search_read")

        assert exc_info.value.status_code == 500


# -- Convenience method tests (bearer) --------------------------------------


class TestConvenienceMethods:
    @pytest.mark.asyncio
    async def test_search_read_passes_params(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=[])

        _mock_client(client, handler)
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

        _mock_client(client, handler)
        await client.search_read("res.partner")

        body = json.loads(requests[0].content)
        assert body == {}

    @pytest.mark.asyncio
    async def test_read_passes_fields(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json=[{"id": 1, "name": "Test"}])

        _mock_client(client, handler)
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

        _mock_client(client, handler)
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

        _mock_client(client, handler)
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

        _mock_client(client, handler)
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

        _mock_client(client, handler)
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

        _mock_client(client, handler)
        result = await client.unlink("res.partner", [1, 2])

        assert result is True
        assert requests[0].url.path == "/json/2/res.partner/unlink"
        body = json.loads(requests[0].content)
        assert body == {"ids": [1, 2]}


# -- Doc endpoint tests ------------------------------------------------------


class TestDocMethods:
    @pytest.mark.asyncio
    async def test_bearer_uses_doc_bearer_prefix(self, client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={})

        _mock_client(client, handler)
        await client.get_doc_index()
        assert requests[0].url.path == "/doc-bearer/index.json"

        await client.get_doc("res.partner")
        assert requests[1].url.path == "/doc-bearer/res.partner.json"

    @pytest.mark.asyncio
    async def test_session_uses_doc_prefix(self, session_client):
        requests = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, json={})

        _mock_session_client(session_client, handler)
        await session_client.get_doc_index()
        assert requests[0].url.path == "/doc/index.json"

        await session_client.get_doc("res.partner")
        assert requests[1].url.path == "/doc/res.partner.json"
