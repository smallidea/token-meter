# -*- coding: utf-8 -*-
import unittest

from custom.grokbot_adapter import GrokbotRuntimeAdapter
from custom.doubao_adapter import DoubaoRuntimeAdapter
from custom.models_pricing import get_price, calculate_cost
from desktop.tabs.tools_tab import provider_label


class TestCustomAdapters(unittest.TestCase):
    def test_pricing(self):
        p_grok = get_price("grok-2")
        self.assertEqual(p_grok["input"], 2.00)
        self.assertEqual(p_grok["output"], 10.00)

        p_doubao = get_price("doubao-1.5-pro")
        self.assertEqual(p_doubao["input"], 0.12)
        self.assertEqual(p_doubao["output"], 0.30)

        cost = calculate_cost(100_000, 100_000, 0, 0, "grok-2")
        self.assertGreater(cost, 0)

    def test_grokbot_adapter_discovery(self):
        adapter = GrokbotRuntimeAdapter()
        sources = adapter.discover_legacy()
        self.assertIsInstance(sources, tuple)
        if sources:
            s0 = sources[0]
            self.assertEqual(s0["provider"], "grokbot")
            self.assertIn("tokens", s0)
            self.assertIn("cost", s0)

    def test_doubao_adapter_discovery(self):
        adapter = DoubaoRuntimeAdapter()
        sources = adapter.discover_legacy()
        self.assertIsInstance(sources, tuple)
        if sources:
            s0 = sources[0]
            self.assertEqual(s0["provider"], "doubao")
            self.assertIn("tokens", s0)
            self.assertIn("cost", s0)

    def test_provider_labels(self):
        self.assertEqual(provider_label("grokbot"), "Grok Bot")
        self.assertEqual(provider_label("doubao"), "豆包 (Doubao)")
        self.assertEqual(provider_label("traecn"), "Trae CN")
        self.assertEqual(provider_label("workbuddy"), "WorkBuddy")


if __name__ == "__main__":
    unittest.main()
