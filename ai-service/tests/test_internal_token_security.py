"""Middleware regressions with synthetic values; no network or application startup."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from starlette.requests import Request
from starlette.responses import Response
from app import main
from app.config import Settings

class InternalTokenSecurityTests(unittest.IsolatedAsyncioTestCase):
    def request(self, token=None):
        headers = [] if token is None else [(b"x-internal-token", token.encode())]
        return Request({"type": "http", "path": "/v1/test", "headers": headers, "scheme": "http", "query_string": b""})

    async def test_empty_configuration_and_empty_header_are_rejected(self):
        next_handler = AsyncMock(return_value=Response(status_code=200))
        with patch.object(main, "settings", SimpleNamespace(internal_token="")):
            result = await main.internal_token_guard(self.request(""), next_handler)
        self.assertEqual(result.status_code, 401)
        next_handler.assert_not_awaited()

    async def test_missing_header_is_rejected(self):
        next_handler = AsyncMock(return_value=Response(status_code=200))
        with patch.object(main, "settings", SimpleNamespace(internal_token="synthetic-test-value")):
            result = await main.internal_token_guard(self.request(), next_handler)
        self.assertEqual(result.status_code, 401)
        next_handler.assert_not_awaited()

    async def test_explicit_matching_token_is_accepted(self):
        next_handler = AsyncMock(return_value=Response(status_code=200))
        with patch.object(main, "settings", SimpleNamespace(internal_token="synthetic-test-value")):
            result = await main.internal_token_guard(self.request("synthetic-test-value"), next_handler)
        self.assertEqual(result.status_code, 200)
        next_handler.assert_awaited_once()

    def test_no_published_default_internal_token(self):
        self.assertEqual(Settings.model_fields["internal_token"].default, "")

if __name__ == "__main__":
    unittest.main()
