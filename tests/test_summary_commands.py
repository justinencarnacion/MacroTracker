import unittest
from types import SimpleNamespace

from bot.commands.summaries import SummaryCommands


class SummaryCommandsTests(unittest.TestCase):
    def test_registers_expected_slash_commands(self):
        cog = SummaryCommands(SimpleNamespace())
        names = sorted(command.qualified_name for command in cog.walk_app_commands())
        self.assertEqual(names, ["goals", "goals set", "goals show", "today", "week"])

    def test_commands_work_in_dms_and_servers(self):
        cog = SummaryCommands(SimpleNamespace())
        for command in cog.get_app_commands():
            contexts = command.allowed_contexts
            self.assertTrue(contexts.guild and contexts.dm_channel, command.name)

    def test_goal_options_are_optional(self):
        cog = SummaryCommands(SimpleNamespace())
        goals_set = next(c for c in cog.walk_app_commands() if c.qualified_name == "goals set")
        self.assertTrue(all(not p.required for p in goals_set.parameters))


if __name__ == "__main__":
    unittest.main()
