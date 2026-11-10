"""Telling a brief outage from a daily quota or a permanent failure."""

import unittest
from datetime import datetime

import requests

from bot.ai_parser import is_daily_quota
from bot.bot import QUOTA_TIMEZONE, until_quota_reset
from sheets.sheet_manager import is_temporary_error
from testing.fakes import gemini, spreadsheet


class DailyQuotaTests(unittest.TestCase):
    def test_only_a_429_naming_the_daily_quota_counts(self):
        self.assertTrue(is_daily_quota(gemini.api_error(429, daily_quota=True)))
        self.assertFalse(is_daily_quota(gemini.api_error(429)))  # per-minute limit
        self.assertFalse(is_daily_quota(gemini.api_error(503)))

    def test_time_until_midnight_pacific(self):
        def at(hour, minute=0):
            return until_quota_reset(datetime(2026, 11, 10, hour, minute, tzinfo=QUOTA_TIMEZONE))

        self.assertEqual(at(19), "about 5 hours")
        self.assertEqual(at(23), "about 1 hour")
        self.assertEqual(at(23, 30), "under an hour")


class TemporarySheetsErrorTests(unittest.TestCase):
    def test_rate_limits_server_errors_and_network_trouble_are_temporary(self):
        for error in (spreadsheet.api_error(429), spreadsheet.api_error(503),
                      requests.ConnectionError(), requests.Timeout()):
            self.assertTrue(is_temporary_error(error), error)

    def test_permission_and_other_errors_are_not(self):
        for error in (spreadsheet.api_error(403), ValueError("bad row")):
            self.assertFalse(is_temporary_error(error), error)
