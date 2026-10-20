"""Generate the website's Discord demo from the real bot code.

Uses the same chart renderers and embed builders as the bot, with sample
meals, so the demo always matches what the bot actually sends.

Run from the project root:  python web/scripts/generate_demo.py
"""

import json
from datetime import date
from pathlib import Path

from bot import embeds, formatting
from charts.today import render_today
from charts.week import render_week
from tracking.summaries import summarize_day, summarize_week

WEB = Path(__file__).resolve().parent.parent
GOALS = {"calories": 1900, "protein": 140, "carbs": 200, "fat": 60}
TODAY = date(2026, 10, 15)  # a Thursday


def meal(date_time, name, calories, protein, carbs, fat):
    return {"date_time": date_time, "meal_name": name, "calories": calories,
            "protein": protein, "carbs": carbs, "fat": fat}


MEALS = [
    meal("2026-10-12 12:30", "Burrito bowl", 1850, 130, 190, 55),
    meal("2026-10-13 19:00", "Pizza night", 2300, 150, 260, 80),
    meal("2026-10-15 08:10", "Fuji apple", 115, 0.5, 29, 0.3),
    meal("2026-10-15 12:40", "Chicken thigh and white rice", 865, 55, 92, 30),
]


def embed_data(embed, image_name):
    return {
        "title": embed.title,
        "description": embed.description,
        "fields": [{"name": f.name, "value": f.value} for f in embed.fields],
        "image": image_name,
    }


def main():
    day = summarize_day(MEALS, TODAY, GOALS)
    week = summarize_week(MEALS, TODAY, GOALS)
    (WEB / "public" / "demo").mkdir(parents=True, exist_ok=True)
    (WEB / "public" / "demo" / "today.png").write_bytes(render_today(day))
    (WEB / "public" / "demo" / "week.png").write_bytes(render_week(week))

    # Today's totals before lunch, for the "Left today" line under the lunch log.
    lunch = MEALS[-1]
    demo = {
        "logged": {
            "message": "270g chicken thigh with skin and bone, 250g cooked white rice",
            "reply": f"✅ Logged! (AI Estimated)\nMeal: {lunch['meal_name']}\n"
                     f"{formatting.macro_line(lunch)}",
            "leftToday": formatting.format_left_today(day.remaining).replace("**", ""),
        },
        "today": embed_data(embeds.today_embed(day), "today.png"),
        "week": embed_data(embeds.week_embed(week), "week.png"),
    }
    out = WEB / "src" / "content" / "demo.json"
    out.write_text(json.dumps(demo, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(WEB.parent)} and public/demo/*.png")


if __name__ == "__main__":
    main()
