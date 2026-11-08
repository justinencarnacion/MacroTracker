"""Registers scenarios and gives them short, readable checks.

    @scenario("A member can log a meal")
    async def logs_a_meal(harness):
        alice = harness.user("Alice")
        said(await alice.dm("2 eggs"), "Logged!")

Each scenario gets its own fresh bot, so scenarios can't affect each other.
"""

from dataclasses import dataclass, field

# Generous, so scenarios exercise features; the rate limit has its own scenario.
DEFAULT_OPTIONS = {"rate_limit": (1000, 60)}

SCENARIOS = []


@dataclass
class Scenario:
    name: str
    group: str
    run: object
    options: dict = field(default_factory=dict)


def scenario(name, **harness_options):
    """Mark an async function taking a Harness as a scenario."""

    def register(function):
        group = function.__module__.rsplit(".", 1)[-1].replace("_", " ").capitalize()
        SCENARIOS.append(Scenario(name, group, function, {**DEFAULT_OPTIONS, **harness_options}))
        return function

    return register


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def equal(actual, wanted, what="value"):
    expect(actual == wanted, f"{what}: wanted {wanted!r}, got {actual!r}")


def said(sent, *phrases):
    """The bot replied, and the reply contains every phrase. Returns the reply."""
    expect(sent is not None, f"the bot sent nothing (expected {phrases!r})")
    for phrase in phrases:
        expect(phrase in sent.text, f"reply is missing {phrase!r}; it said: {sent.text[:300]!r}")
    return sent


def not_said(sent, *phrases):
    for phrase in phrases:
        expect(phrase not in sent.text, f"reply should not contain {phrase!r}: {sent.text[:300]!r}")
    return sent


def is_card(sent, *phrases):
    """A summary card: embed, chart image, and the [Today] [Week] buttons."""
    said(sent, *phrases)
    expect(sent.embed is not None, "the card has no embed")
    expect(sent.image, "the card has no chart image")
    equal(sent.labels(), ["Today", "Week"], "buttons")
    return sent
