"""Mass cancellation must not exhaust BACnet invoke identifiers."""
import asyncio
import ast
import logging
import unittest
from pathlib import Path
from types import SimpleNamespace

class CleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_600_unsubscribes_are_limited_and_event_loop_stays_responsive(self):
        source = Path(__file__).parents[1] / "engelsoft_bacstac/rootfs/usr/bin/BACnetIOHandler.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BACnetIOHandler")
        method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_bounded_cov_unsubscribe")
        scope = {"asyncio": asyncio, "LOGGER": logging.getLogger("test")}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), scope)
        active = peak = completed = 0
        async def request(value):
            nonlocal active, peak, completed
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(.001)
            active -= 1
            completed += 1
        handler = SimpleNamespace(_cov_unsubscribe_slots=asyncio.Semaphore(4), request=request)
        await asyncio.wait_for(asyncio.gather(*(scope["_bounded_cov_unsubscribe"](handler, n) for n in range(600))), 5)
        self.assertEqual(completed, 600)
        self.assertLessEqual(peak, 4)
