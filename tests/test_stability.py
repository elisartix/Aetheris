import asyncio
import unittest
from types import SimpleNamespace

from aetheris.stability import module_health_snapshot


class StabilityTests(unittest.TestCase):
    def test_module_health_snapshot_marks_failed_user_module(self):
        mod = SimpleNamespace(name="Broken", __origin__="<file>")
        result = module_health_snapshot([mod], {id(mod): "boom"})
        self.assertEqual(result, {"loaded": 0, "failed": 1, "core_failed": 0})

    def test_module_health_snapshot_does_not_count_healthy_core_as_failed(self):
        mod = SimpleNamespace(name="Core", __origin__="<core>")
        result = module_health_snapshot([mod], {})
        self.assertEqual(result, {"loaded": 1, "failed": 0, "core_failed": 0})

    def test_module_health_snapshot_includes_removed_failed_modules(self):
        result = module_health_snapshot([], {}, failed_module_count=2)
        self.assertEqual(result, {"loaded": 0, "failed": 2, "core_failed": 0})
