import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "health_report", Path(__file__).resolve().parent.parent / "deploy" / "health_report.py")
health_report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_report)


def collected(**overrides):
    data = {
        "system": {"model": "Raspberry Pi 4", "uptime_hours": 5, "temperature_c": 45.0,
                   "throttled": 0, "cpu_count": 4, "load": [0.1, 0.1, 0.1],
                   "mem_total_mb": 1900, "mem_available_mb": 1400,
                   "swap_total_mb": 0, "swap_free_mb": 0, "disk_total_gb": 15.0, "disk_free_gb": 8.0},
        "bot": {"found": True, "status": "running", "started_at": "2026-10-22T10:00:00Z",
                "restarts": 0, "cpu_percent": "0.1", "memory_mb": 180, "image_mb": 512,
                "log_errors_24h": 0, "commit": "abc1234def", "commit_subject": "Something"},
        "usage": {"users": {"total": 3, "with_goals": 2, "with_timezone": 1, "active_24h": 1, "active_7d": 2},
                  "windows": {"24h": {"meal": {"logged": 2},
                                      "ai_call": {"gemini-3.6-flash:ok": 3}},
                              "7d": {"meal": {"logged": 5}}},
                  "per_day": {}, "quota_today": {"gemini-3.6-flash": 3}},
    }
    for path, value in overrides.items():
        section, key = path.split(".")
        data[section][key] = value
    return data


class HealthReportTests(unittest.TestCase):
    def warnings(self, data, **kwargs):
        return [why for _, why in health_report.build_report(data, **kwargs).warnings]

    def test_healthy_system_has_no_warnings(self):
        report = health_report.build_report(collected(), github_commit="abc1234def", behind="0")
        self.assertEqual(report.warnings, [])
        self.assertIn("All healthy", report.render())

    def test_flags_hot_pi_low_memory_and_throttling(self):
        found = self.warnings(collected(**{"system.temperature_c": 82.0,
                                           "system.mem_available_mb": 120,
                                           "system.throttled": 0x50005}))
        self.assertTrue(any("temperature" in w for w in found))
        self.assertTrue(any("RAM" in w for w in found))
        self.assertTrue(any("under-voltage now" in w for w in found))

    def test_flags_bot_problems_and_outdated_deploy(self):
        found = self.warnings(collected(**{"bot.restarts": 2, "bot.log_errors_24h": 4}),
                              github_commit="fffffff", behind="3")
        self.assertTrue(any("restarted 2" in w for w in found))
        self.assertTrue(any("4 error" in w for w in found))
        self.assertTrue(any("3 commit(s) behind" in w for w in found))

    def test_flags_quota_use_and_rate_limits(self):
        data = collected()
        data["usage"]["quota_today"] = {"gemini-3.6-flash": 16}
        data["usage"]["windows"]["24h"]["ai_call"] = {"gemini-3.6-flash:rate_limited": 2}
        found = self.warnings(data)
        self.assertTrue(any("16 of 20" in w for w in found))
        self.assertTrue(any("quota (429) 2" in w for w in found))

    def test_works_before_usage_tracking_is_deployed(self):
        data = collected()
        data["usage"] = {"users": {"total": 3, "with_goals": 1, "with_timezone": 0}, "tracking": False}
        self.assertIn("Usage tracking starts after the next deploy", health_report.build_report(data).render())

    def test_history_csv_gets_header_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            health_report.append_history(str(path), collected(), [])
            health_report.append_history(str(path), collected(), [("warn", "x")])
            with path.open() as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["meals_logged_24h"], "2")
        self.assertEqual(rows[1]["warnings"], "1")


if __name__ == "__main__":
    unittest.main()
