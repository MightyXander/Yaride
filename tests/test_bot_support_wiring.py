"""Сборка bot_support после контейнера."""

from __future__ import annotations

from unittest import TestCase

import app.bot_support as bot_support
from app.bootstrap import build_container
from app.navigation_flow import NavigationFlow
from app.trip_flow import TripFlowOrchestrator


class BotSupportWiringTests(TestCase):
    def test_configure_builds_flow_and_navigation(self) -> None:
        """configure() возвращает готовые объекты; глобалы больше не используются."""
        container = build_container()
        flow, nav = bot_support.configure(container)
        self.assertIsInstance(flow, TripFlowOrchestrator)
        self.assertIsInstance(nav, NavigationFlow)
        self.assertIsNotNone(flow)
        self.assertIsNotNone(nav)
