"""BanMiddleware: забаненный пользователь не доходит до хендлера, обычный — доходит."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.middlewares import BanMiddleware


class _RepoStub:
    def __init__(self, banned_ids: set[int]) -> None:
        self.users = SimpleNamespace(is_banned=lambda tg: tg in banned_ids)


class BanMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_banned_user_blocked(self) -> None:
        mw = BanMiddleware(_RepoStub({999}))
        called = False

        async def handler(event, data):
            nonlocal called
            called = True
            return "handled"

        data = {"event_from_user": SimpleNamespace(id=999)}
        result = await mw(handler, SimpleNamespace(), data)
        self.assertIsNone(result)
        self.assertFalse(called)

    async def test_regular_user_passes(self) -> None:
        mw = BanMiddleware(_RepoStub({999}))
        called = False

        async def handler(event, data):
            nonlocal called
            called = True
            return "handled"

        data = {"event_from_user": SimpleNamespace(id=111)}
        result = await mw(handler, SimpleNamespace(), data)
        self.assertEqual(result, "handled")
        self.assertTrue(called)

    async def test_no_user_passes(self) -> None:
        mw = BanMiddleware(_RepoStub({999}))

        async def handler(event, data):
            return "handled"

        result = await mw(handler, SimpleNamespace(), {})
        self.assertEqual(result, "handled")


if __name__ == "__main__":
    unittest.main()
