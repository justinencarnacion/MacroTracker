"""Formats the JSON from health_collect.py into a report with warnings, and
appends a summary row to a CSV history file. Run by deploy/health.sh.

Usage: health_report.py --history PATH [--github-commit SHA] [--behind N] < collected.json
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

# Warning thresholds: (warn, critical). Tune here.
TEMP_C = (70, 80)
MEM_AVAILABLE_MB = (300, 150)  # warn when below
DISK_FREE_GB = (2.0, 1.0)  # warn when below
LOAD_PER_CPU = 0.75  # warn when 1-minute load exceeds this x CPU count
FREE_TIER_DAILY = int(os.getenv("GEMINI_FREE_TIER_DAILY", "20"))  # requests per model per day
QUOTA_WARN_FRACTION = 0.75

THROTTLE_FLAGS = {
    0x1: "under-voltage now", 0x2: "CPU frequency capped now", 0x4: "throttled now",
    0x8: "temperature limit now", 0x10000: "under-voltage since boot",
    0x20000: "frequency capped since boot", 0x40000: "throttled since boot",
    0x80000: "temperature limit since boot",
}

COLOR = sys.stdout.isatty() and not os.getenv("NO_COLOR")


def paint(text, code):
    return f"\033[{code}m{text}\033[0m" if COLOR else text


OK, WARN, CRIT = paint("✅", "32"), paint("⚠️ ", "33"), paint("❌", "31")


class Report:
    def __init__(self):
        self.lines = []
        self.warnings = []

    def section(self, title):
        self.lines.append("")
        self.lines.append(paint(f"== {title} ==", "1"))

    def row(self, label, value, level=None, why=None):
        icon = {None: "  ", "ok": OK, "warn": WARN, "crit": CRIT}[level]
        self.lines.append(f"{icon} {label:<26} {value}")
        if level in ("warn", "crit") and why:
            self.warnings.append((level, why))

    def text(self, line):
        self.lines.append(f"   {line}")

    def render(self):
        out = list(self.lines)
        out.append("")
        if self.warnings:
            out.append(paint(f"== {len(self.warnings)} thing(s) need attention ==", "1"))
            for level, why in self.warnings:
                out.append(f"{CRIT if level == 'crit' else WARN} {why}")
        else:
            out.append(paint("== All healthy ==", "1;32"))
        return "\n".join(out)


def level_high(value, limits):
    if value is None:
        return None
    return "crit" if value >= limits[1] else "warn" if value >= limits[0] else "ok"


def level_low(value, limits):
    if value is None:
        return None
    return "crit" if value < limits[1] else "warn" if value < limits[0] else "ok"


def total(counts):
    return sum((counts or {}).values())


def ai_by_model(counts):
    """{'model:outcome': n} -> {model: {outcome: n}}"""
    models = {}
    for label, count in (counts or {}).items():
        model, _, outcome = label.rpartition(":")
        models.setdefault(model, {})[outcome] = models.get(model, {}).get(outcome, 0) + count
    return models


def system_section(report, system):
    report.section("RASPBERRY PI")
    report.row("Model", system.get("model") or "?")
    report.row("Uptime", f"{system.get('uptime_hours', '?')} hours")

    temp = system.get("temperature_c")
    level = level_high(temp, TEMP_C)
    report.row("Temperature", f"{temp}°C" if temp is not None else "?", level,
               f"Pi temperature {temp}°C (warn at {TEMP_C[0]}°C)")

    flags = system.get("throttled")
    if flags is None:
        report.row("Power / throttling", "?")
    elif flags == 0:
        report.row("Power / throttling", "0x0 (none)", "ok")
    else:
        names = [name for bit, name in THROTTLE_FLAGS.items() if flags & bit]
        now = flags & 0xF
        report.row("Power / throttling", f"{hex(flags)}: {', '.join(names)}", "crit" if now else "warn",
                   f"Throttling {hex(flags)} ({', '.join(names)}): check the power supply and cooling")

    load, cpus = system.get("load"), system.get("cpu_count") or 1
    if load:
        busy = load[0] > cpus * LOAD_PER_CPU
        report.row("CPU load (1/5/15 min)", f"{load[0]} / {load[1]} / {load[2]}  ({cpus} cores)",
                   "warn" if busy else "ok", f"High CPU load {load[0]} on {cpus} cores")

    available, memory_total = system.get("mem_available_mb"), system.get("mem_total_mb")
    report.row("RAM available", f"{available} MB of {memory_total} MB",
               level_low(available, MEM_AVAILABLE_MB), f"Only {available} MB RAM available")
    swap_total = system.get("swap_total_mb") or 0
    if swap_total:
        used = swap_total - (system.get("swap_free_mb") or 0)
        report.row("Swap used", f"{used} MB of {swap_total} MB")

    free = system.get("disk_free_gb")
    report.row("SD card free", f"{free} GB of {system.get('disk_total_gb')} GB",
               level_low(free, DISK_FREE_GB), f"Only {free} GB free on the SD card")


def bot_section(report, bot, github_commit, behind):
    report.section("BOT")
    if not bot.get("found"):
        report.row("Container", "not found", "crit", "The macrotracker container doesn't exist; deploy the bot")
        return
    running = bot.get("status") == "running"
    report.row("Status", f"{bot.get('status')} since {str(bot.get('started_at'))[:19].replace('T', ' ')} UTC",
               "ok" if running else "crit", f"Bot container is {bot.get('status')}")
    restarts = bot.get("restarts", 0)
    report.row("Crash restarts", restarts, "warn" if restarts else "ok",
               f"The bot restarted {restarts} time(s) after crashing; check the logs")
    report.row("Bot memory", f"{bot.get('memory_mb', '?')} MB")
    report.row("Bot CPU", f"{bot.get('cpu_percent', '?')}%")
    report.row("Image size", f"{bot.get('image_mb', '?')} MB")

    commit = (bot.get("commit") or "?")[:7]
    subject = bot.get("commit_subject") or ""
    if github_commit and bot.get("commit") == github_commit:
        report.row("Deployed version", f"{commit} {subject} (matches GitHub)", "ok")
    elif github_commit:
        detail = f"{behind} commit(s) behind GitHub" if behind and behind != "?" else "differs from GitHub"
        report.row("Deployed version", f"{commit} {subject} ({detail})", "warn",
                   f"The Pi runs {commit}, {detail}; run ./deploy/deploy.sh if that's unintended")
    else:
        report.row("Deployed version", f"{commit} {subject}")

    errors = bot.get("log_errors_24h", 0)
    report.row("Errors in logs (24h)", errors, "warn" if errors else "ok",
               f"{errors} error(s) in the bot's logs in the last 24 hours")


def usage_section(report, usage):
    users = (usage or {}).get("users") or {}
    report.section("USERS")
    report.row("Registered users", users.get("total", "?"))
    report.row("With goals set", users.get("with_goals", "?"))
    report.row("With timezone set", users.get("with_timezone", "?"))
    if usage.get("tracking") is False:
        report.text("Usage tracking starts after the next deploy of the bot.")
        return
    report.row("Active users", f"{users.get('active_24h', 0)} (24h) · {users.get('active_7d', 0)} (7 days)")
    welcome = usage["windows"]["7d"].get("welcome", {})
    if welcome:
        closed = welcome.get("dms_closed", 0)
        report.row("New members welcomed (7d)", f"{welcome.get('sent', 0)} sent · {closed} had DMs closed")

    day, week = usage["windows"]["24h"], usage["windows"]["7d"]
    report.section("REQUESTS                     24 hours   7 days")
    for name, label in (("dm", "DMs"), ("command", "Slash commands"), ("button", "Button presses")):
        report.row(label, f"{total(day.get(name)):>8} {total(week.get(name)):>8}")
    for kind in ("logged", "edited", "deleted"):
        report.row(f"Meals {kind}", f"{day.get('meal', {}).get(kind, 0):>8} {week.get('meal', {}).get(kind, 0):>8}")
    refused_day, refused_week = day.get("refused", {}), week.get("refused", {})
    report.row("Refused: not a member", f"{refused_day.get('not_member', 0):>8} {refused_week.get('not_member', 0):>8}")
    report.row("Refused: too fast", f"{refused_day.get('rate_limited', 0):>8} {refused_week.get('rate_limited', 0):>8}")
    commands = week.get("command", {})
    if commands:
        top = ", ".join(f"/{name} {count}" for name, count in sorted(commands.items(), key=lambda kv: -kv[1]))
        report.text(f"Commands (7 days): {top}")

    ai_section(report, day, week, usage.get("quota_today", {}))
    per_day_section(report, usage.get("per_day", {}))


def ai_section(report, day, week, quota_today):
    report.section("AI (GEMINI)")
    requests_day, requests_week = day.get("request", {}), week.get("request", {})
    for key, label in (("answered", "Answered"), ("all_busy", "All models busy"),
                       ("unreadable", "Couldn't understand"), ("error", "Other errors")):
        value_day, value_week = requests_day.get(key, 0), requests_week.get(key, 0)
        bad = key in ("all_busy", "error") and value_day > 0
        report.row(label, f"{value_day:>8} {value_week:>8}", "warn" if bad else None,
                   f"{value_day} request(s) failed in the last 24h ({label.lower()})")

    report.text("")
    report.text(f"{'Model attempts (24h)':<26}{'ok':>5}{'busy':>6}{'429':>5}{'err':>5}   used today / {FREE_TIER_DAILY}")
    models = ai_by_model(day.get("ai_call"))
    for model in sorted(set(models) | set(quota_today)):
        outcomes = models.get(model, {})
        used = quota_today.get(model, 0)
        level = "warn" if used >= FREE_TIER_DAILY * QUOTA_WARN_FRACTION else None
        limited = outcomes.get("rate_limited", 0)
        line = (f"{model:<26}{outcomes.get('ok', 0):>5}{outcomes.get('overloaded', 0):>6}"
                f"{limited:>5}{outcomes.get('error', 0):>5}   {used:>4}")
        report.row(line, "", level, f"{model} has used {used} of {FREE_TIER_DAILY} free requests today")
        if limited:
            report.warnings.append(("warn", f"{model} hit its quota (429) {limited} time(s) in the last 24h"))
    if not models and not quota_today:
        report.text("No AI requests yet.")


def per_day_section(report, per_day):
    if not per_day:
        return
    report.section("LAST 7 DAYS (per day)")
    report.text(f"{'Day':<12}{'DMs':>5}{'Cmds':>6}{'Meals':>7}{'AI ok':>7}{'AI fail':>8}")
    for day, names in per_day.items():
        ai = names.get("ai_call", {})
        ok = sum(count for label, count in ai.items() if label.endswith(":ok"))
        report.text(f"{day:<12}{total(names.get('dm')):>5}{total(names.get('command')):>6}"
                    f"{names.get('meal', {}).get('logged', 0):>7}{ok:>7}{total(ai) - ok:>8}")


HISTORY_FIELDS = [
    "timestamp", "temperature_c", "throttled", "load_1m", "mem_available_mb", "disk_free_gb",
    "bot_status", "restarts", "bot_memory_mb", "deployed_commit", "users_total", "active_24h",
    "dms_24h", "commands_24h", "meals_logged_24h", "ai_ok_24h", "ai_failed_24h",
    "ai_rate_limited_24h", "all_busy_24h", "warnings",
]


def append_history(path, data, warnings):
    system, bot, usage = data["system"], data["bot"], data.get("usage") or {}
    day = (usage.get("windows") or {}).get("24h", {})
    ai = day.get("ai_call", {})
    ai_ok = sum(count for label, count in ai.items() if label.endswith(":ok"))
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "temperature_c": system.get("temperature_c"),
        "throttled": hex(system["throttled"]) if system.get("throttled") is not None else "",
        "load_1m": (system.get("load") or [""])[0],
        "mem_available_mb": system.get("mem_available_mb"),
        "disk_free_gb": system.get("disk_free_gb"),
        "bot_status": bot.get("status", "missing"),
        "restarts": bot.get("restarts", ""),
        "bot_memory_mb": bot.get("memory_mb", ""),
        "deployed_commit": (bot.get("commit") or "")[:7],
        "users_total": (usage.get("users") or {}).get("total", ""),
        "active_24h": (usage.get("users") or {}).get("active_24h", ""),
        "dms_24h": total(day.get("dm")),
        "commands_24h": total(day.get("command")),
        "meals_logged_24h": day.get("meal", {}).get("logged", 0),
        "ai_ok_24h": ai_ok,
        "ai_failed_24h": total(ai) - ai_ok,
        "ai_rate_limited_24h": sum(c for label, c in ai.items() if label.endswith(":rate_limited")),
        "all_busy_24h": day.get("request", {}).get("all_busy", 0),
        "warnings": len(warnings),
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new_file = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def build_report(data, github_commit=None, behind=None):
    report = Report()
    system_section(report, data.get("system") or {})
    bot_section(report, data.get("bot") or {}, github_commit, behind)
    usage_section(report, data.get("usage") or {})
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", required=True)
    parser.add_argument("--github-commit")
    parser.add_argument("--behind")
    args = parser.parse_args()

    data = json.load(sys.stdin)
    report = build_report(data, args.github_commit, args.behind)
    print(report.render())
    append_history(args.history, data, report.warnings)
    print(f"\nSaved to {args.history}")
    return 1 if any(level == "crit" for level, _ in report.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
