"""
Generates tomorrow's study plan from current prep_profile.
Called after batch_analyse.py completes.
Writes to data/study_plan.json.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from datetime import datetime, date, timezone
import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

PROFILE_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_profile.json"
PLAN_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "study_plan.json"
CONFIG_PATH = Path(os.getenv("PROJECT_PATH", ".")) / "data" / "prep_config.json"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "plan_generation.txt"

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"total_days": 10, "daily_hours": 6, "start_date": date.today().isoformat()}


def days_remaining() -> int:
    config = load_config()
    start_str = config.get("start_date") or date.today().isoformat()
    total = int(config.get("total_days", 10))
    start = date.fromisoformat(start_str)
    elapsed = max(0, (date.today() - start).days)
    return max(1, total - elapsed)


def current_day_number() -> int:
    config = load_config()
    start_str = config.get("start_date") or date.today().isoformat()
    start = date.fromisoformat(start_str)
    elapsed = max(0, (date.today() - start).days)
    return elapsed + 1


def generate_plan(available_hours: float | None = None) -> dict:
    if not PROFILE_PATH.exists():
        print("No prep profile found. Run batch_analyse.py first.")
        return {"message": "No prep profile yet. Complete a diagnostic session and run batch analysis first."}

    try:
        profile = json.loads(PROFILE_PATH.read_text())
    except Exception:
        return {"message": "Prep profile is corrupted. Run batch analysis again to rebuild it."}

    config = load_config()
    if available_hours is None:
        available_hours = float(config.get("daily_hours", 6))

    day_number = current_day_number()
    remaining = days_remaining()
    total_days = int(config.get("total_days", 10))

    prompt_template = PROMPT_PATH.read_text()
    prompt = (
        prompt_template
        .replace("{{prep_profile}}", json.dumps(profile, indent=2))
        .replace("{{day_number}}", str(day_number))
        .replace("{{days_remaining}}", str(remaining))
        .replace("{{total_days}}", str(total_days))
        .replace("{{available_hours}}", str(available_hours))
        .replace("{{phase}}", profile.get("phase", "diagnostic"))
    )

    response = client.messages.create(
        model=os.getenv("AI_MODEL_SMART", "claude-sonnet-4-6"),
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()

    try:
        start_idx, end_idx = raw.find("{"), raw.rfind("}") + 1
        plan = json.loads(raw[start_idx:end_idx])
    except Exception as e:
        print(f"Plan JSON parse failed: {e}")
        return {"message": "Plan generation failed — Claude returned unexpected format. Try again."}

    plan["generated_at"] = datetime.now(timezone.utc).isoformat()
    plan["day_number"] = day_number
    plan["days_remaining"] = remaining
    plan["total_days"] = total_days

    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(json.dumps(plan, indent=2))
    print(f"✅ Plan generated for Day {day_number}/{total_days}. Sessions: {len(plan.get('sessions', []))}")
    return plan


if __name__ == "__main__":
    import sys
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else None
    generate_plan(hours)
