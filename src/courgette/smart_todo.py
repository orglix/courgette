"""Combines the deterministic scheduler (rappels.py) with the AI judgment
layer (llm.py) to decide which watering tasks actually show up today.

Non-watering tasks (semis, plantation, taille, recolte) pass through
unchanged — the AI layer only ever refines watering decisions.

Fails safe: if the location isn't configured, the weather API is
unreachable, or the LLM call fails, we fall back to the deterministic
schedule as-is rather than silently dropping tasks.
"""

import logging
from datetime import date

from sqlmodel import Session

from courgette import llm
from courgette import rappels
from courgette import weather
from courgette.models import TypeEvenement

logger = logging.getLogger(__name__)


def todays_smart_tasks(session: Session, today: date | None = None) -> list[dict]:
    today = today or date.today()
    all_tasks = rappels.taches_du_jour(session, today)

    watering_tasks = [t for t in all_tasks if t["type"] == TypeEvenement.ARROSAGE.value]
    other_tasks = [t for t in all_tasks if t["type"] != TypeEvenement.ARROSAGE.value]

    if not watering_tasks:
        return all_tasks

    try:
        forecast = weather.get_weather()
    except RuntimeError as exc:
        logger.warning("Weather unavailable, keeping watering tasks as-is: %s", exc)
        return all_tasks

    weather_summary = {
        "recent_rainfall_mm": weather.recent_rainfall_mm(forecast, today),
        "rainfall_expected_today_mm": weather.rainfall_expected_today_mm(forecast, today),
    }

    try:
        decisions = {
            d.plante_jardin_id: d for d in llm.decide_watering(watering_tasks, weather_summary)
        }
    except Exception as exc:  # noqa: BLE001 — any LLM/parsing failure should fail safe, not crash the todo list
        logger.warning("LLM watering decision failed, keeping watering tasks as-is: %s", exc)
        return all_tasks

    kept_watering_tasks = []
    for task in watering_tasks:
        decision = decisions.get(task["plante_jardin_id"])
        if decision is None or decision.keep:
            kept_watering_tasks.append(task)
        else:
            logger.info(
                "Skipping watering for plante_jardin_id=%s: %s",
                task["plante_jardin_id"],
                decision.reason,
            )

    return other_tasks + kept_watering_tasks
