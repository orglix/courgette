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


logger = logging.getLogger(__name__)
 
RAIN_THRESHOLD_MM = 5.0  # same threshold as meteo_sync.py, kept consistent
 
 
def todays_tasks(session: Session, today: date | None = None) -> list[dict]:
    """Returns today's tasks, dropping outdoor watering tasks if significant
    rain is forecast today. Fails safe: any weather/config issue just returns
    the unfiltered schedule rather than blocking the todo list.
    """
    today = today or date.today()
    tasks = rappels.taches_du_jour(session, today)
 
    try:
        forecast = weather.get_weather(past_days=0, forecast_days=1)
        rain_today_mm = weather.rainfall_expected_today_mm(forecast, today)
    except RuntimeError as exc:
        logger.warning("Weather unavailable, keeping watering tasks as-is: %s", exc)
        return tasks
 
    if rain_today_mm < RAIN_THRESHOLD_MM:
        return tasks
 
    logger.info("Rain forecast today (%.1fmm): skipping outdoor watering tasks.", rain_today_mm)
    return [
        t
        for t in tasks
        if not (t["type"] == TypeEvenement.ARROSAGE.value and t["emplacement"] == Emplacement.EXTERIEUR.value)
    ]
 