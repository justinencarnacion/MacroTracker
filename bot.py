from datetime import datetime
import json
import os
from config_manager import load_config, save_config
import discord
from discord.ext import commands
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sheet_manager import (
    connect_sheets,
    get_or_create_worksheet,
    handle_day_transition,
)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Macro Tracker")

ai_client = genai.Client(api_key=GEMINI_API_KEY)
config = load_config()
spreadsheet = connect_sheets(
    {"credentials_file": "credentials.json", "google_sheet_name": SHEET_NAME}
)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

SYSTEM_PROMPT = """
You are an expert nutrition assistant. Analyze the user's message.
Determine if they want to:
1. "LOG_MEAL": Log food or manual macros (e.g. "2 eggs and toast" or "150 cals, 35p").
2. "UPDATE_GOALS": Update their daily goal limits (e.g., "change my goals to 2200 cals, 180p, 200c, 70f").

Return a JSON object with this EXACT structure:
{
  "intent": "LOG_MEAL" or "UPDATE_GOALS",
  "meal_name": "Short descriptive title" (if LOG_MEAL),
  "calories": number,
  "protein": number,
  "carbs": number,
  "fat": number,
  "is_estimation": boolean (true if estimated food, false if exact manual inputs)
}
"""


def parse_input_with_ai(user_text):
    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    return json.loads(response.text)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}! Universal DM Macro Bot is online.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if isinstance(message.channel, discord.DMChannel):
        user_name = message.author.display_name.strip()
        await message.channel.send("🔄 Processing message with AI...")

        try:
            parsed = parse_input_with_ai(message.content)
            intent = parsed.get("intent", "LOG_MEAL")

            # Load latest configuration
            cfg = load_config()
            if "profiles" not in cfg:
                cfg["profiles"] = {}

            # Fallback limits if profile is new
            user_limits = cfg["profiles"].get(
                user_name,
                {
                    "daily_limits": {
                        "calories": 2050,
                        "protein": 160,
                        "carbs": 210,
                        "fat": 70,
                    }
                },
            )["daily_limits"]

            if intent == "UPDATE_GOALS":
                new_limits = {
                    "calories": parsed.get(
                        "calories", user_limits["calories"]
                    ),
                    "protein": parsed.get("protein", user_limits["protein"]),
                    "carbs": parsed.get("carbs", user_limits["carbs"]),
                    "fat": parsed.get("fat", user_limits["fat"]),
                }

                cfg["profiles"][user_name] = {"daily_limits": new_limits}
                save_config(cfg)

                reply = (
                    f"🎯 **Updated Daily Goals for [{user_name}]!**\n"
                    f"**Calories:** {new_limits['calories']} kcal | "
                    f"**P:** {new_limits['protein']}g | "
                    f"**C:** {new_limits['carbs']}g | "
                    f"**F:** {new_limits['fat']}g"
                )
                await message.channel.send(reply)

            else:  # LOG_MEAL
                meal_name = parsed.get("meal_name", "Meal")
                cals = parsed.get("calories", 0)
                p = parsed.get("protein", 0)
                c = parsed.get("carbs", 0)
                f = parsed.get("fat", 0)
                is_est = parsed.get("is_estimation", False)

                sheet = get_or_create_worksheet(spreadsheet, user_name)
                handle_day_transition(sheet, user_limits)

                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.append_row([now_str, meal_name, cals, p, c, f])

                est_tag = " (AI Estimated)" if is_est else " (Manual Input)"
                reply = (
                    f"✅ **Logged to sheet tab [{user_name}]!**{est_tag}\n"
                    f"**Meal:** {meal_name}\n"
                    f"**Calories:** {cals} kcal | **P:** {p}g | **C:** {c}g | **F:** {f}g"
                )
                await message.channel.send(reply)

        except Exception as err:
            await message.channel.send(f"❌ Error: {err}")


bot.run(DISCORD_TOKEN)