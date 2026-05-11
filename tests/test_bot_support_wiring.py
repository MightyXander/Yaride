"""Сборка bot_support после контейнера."""

from __future__ import annotations

from unittest import TestCase

import app.bot_support as bot_support
from app.bootstrap import build_container


class BotSupportWiringTests(TestCase):
    def test_configure_builds_flow_and_navigation(self) -> None:
        container = build_container()
        flow, nav = bot_support.configure(container)
        self.assertIs(flow, bot_support.FLOW_ORCHESTRATOR)
        self.assertIs(nav, bot_support.NAVIGATION_FLOW)
        self.assertIsNotNone(bot_support.FLOW_ORCHESTRATOR)
        self.assertIsNotNone(bot_support.NAVIGATION_FLOW)
