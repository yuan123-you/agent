"""Document downloads must not disclose the internal backend credential."""
import httpx
import pytest

from app.clients.backend_client import BackendClient


@pytest.mark.asyncio
@pytest.mark.parametrize("url, expected_token", [
    ("https://backend.test/files/guide.txt", "test-internal-secret"),
    ("/files/guide.txt", "test-internal-secret"),
    ("https://storage.test/guide.txt?signature=preserved", None),
    ("http://backend.test/files/guide.txt", None),
    ("https://backend.test:8443/files/guide.txt", None),
])
async def test_download_authentication_is_limited_to_backend_origin(url, expected_token):
    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(200, content=b"knowledge base document")

    client = BackendClient()
    await client._long_client.aclose()
    client._long_client = httpx.AsyncClient(
        base_url="https://backend.test",
        headers={"X-Internal-Token": "test-internal-secret"},
        transport=httpx.MockTransport(handle),
    )
    try:
        assert await client.download_file(url) == b"knowledge base document"
        assert seen[0].headers.get("X-Internal-Token") == expected_token
        assert client._long_client.headers["X-Internal-Token"] == "test-internal-secret"
        if "signature=" in url:
            assert seen[0].url.query == b"signature=preserved"
    finally:
        await client._client.aclose()
        await client._long_client.aclose()
