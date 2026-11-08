"""Runs the simulated scenarios against the real bot code: no Discord, Gemini
quota, or Google Sheets involved.

    python -m testing.run                 every scenario
    python -m testing.run --only goals    scenarios whose name or group matches
    python -m testing.run --verbose       also show the bot's logs

Exits 1 if any scenario fails.
"""

import argparse
import asyncio
import importlib
import logging
import pkgutil
import sys
import time
import traceback

import testing.scenarios
from testing.harness import Harness
from testing.scenario import SCENARIOS

SCENARIO_TIMEOUT = 60  # seconds; a hang (e.g. a stuck lock) counts as a failure


def load_scenarios():
    for module in pkgutil.iter_modules(testing.scenarios.__path__):
        importlib.import_module(f"testing.scenarios.{module.name}")


async def run_one(item):
    async with Harness(**item.options) as harness:
        await asyncio.wait_for(item.run(harness), SCENARIO_TIMEOUT)


def failure_text(error):
    if isinstance(error, AssertionError):
        return str(error)
    if isinstance(error, TimeoutError):
        return f"timed out after {SCENARIO_TIMEOUT}s"
    frame = traceback.extract_tb(error.__traceback__)[-1]
    return f"{type(error).__name__}: {error} ({frame.filename}:{frame.lineno})"


def run_all(items):
    """Print each result as it finishes; return the list of failures."""
    failures = []
    group = None
    for item in items:
        if item.group != group:
            group = item.group
            print(f"\n{group}")
        started = time.monotonic()
        try:
            asyncio.run(run_one(item))
        except Exception as error:
            failures.append((item, failure_text(error)))
            print(f"  ❌ {item.name}\n     {failures[-1][1]}")
        else:
            print(f"  ✅ {item.name} ({time.monotonic() - started:.2f}s)")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the simulated bot scenarios.")
    parser.add_argument("--only", help="only run scenarios whose name or group contains this")
    parser.add_argument("--verbose", action="store_true", help="show the bot's logs")
    args = parser.parse_args(argv)

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.disable(logging.CRITICAL)

    load_scenarios()
    items = sorted(SCENARIOS, key=lambda item: item.group)
    if args.only:
        wanted = args.only.lower()
        items = [item for item in items if wanted in f"{item.group} {item.name}".lower()]
    if not items:
        print("No scenarios matched.")
        return 1

    started = time.monotonic()
    failures = run_all(items)
    print(f"\n{len(items) - len(failures)}/{len(items)} passed "
          f"in {time.monotonic() - started:.1f}s")
    if failures:
        print("\nFailed:")
        for item, reason in failures:
            print(f"  ❌ {item.group} / {item.name}: {reason}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
