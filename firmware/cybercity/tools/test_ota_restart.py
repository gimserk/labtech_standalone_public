import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parent.parent / "esp32" / "ota_restart.py"
spec = importlib.util.spec_from_file_location("ota_restart", P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RestartTests(unittest.TestCase):
    def test_no_restart_without_explicit_flags(self):
        calls = []
        with self.assertRaises(ValueError):
            mod.install_and_restart(approve=True, update_fn=lambda **kw: calls.append("update"),
                                    reset_fn=lambda: calls.append("reset"))
        self.assertEqual(calls, [])

    def test_no_restart_without_successful_install(self):
        calls = []
        result = mod.install_and_restart(approve=True, restart=True,
            update_fn=lambda **kw: {"available": False},
            reset_fn=lambda: calls.append("reset"))
        self.assertEqual(result["available"], False)
        self.assertEqual(calls, [])

    def test_failed_install_never_restarts(self):
        calls = []
        def failing(**kwargs):
            raise OSError("download failed")
        with self.assertRaises(OSError):
            mod.install_and_restart(approve=True, restart=True,
                                    update_fn=failing,
                                    reset_fn=lambda: calls.append("reset"))
        self.assertEqual(calls, [])

    def test_success_installs_before_restart(self):
        calls = []
        def updater(**kwargs):
            calls.append("install")
            self.assertEqual(kwargs, {"approve": True})
            return {"installed": 4, "restart_required": True}
        mod.install_and_restart(approve=True, restart=True, update_fn=updater,
                                reset_fn=lambda: calls.append("reset"))
        self.assertEqual(calls, ["install", "reset"])


if __name__ == "__main__":
    unittest.main()
