"""Daily weather synchronization.

Instead of re-deriving "did it rain enough over the last N days" at decision
time (N varies per species' watering frequency, which would mean fetching
and reasoning over a different amount of history for every plant), we
materialize rain as real "arrosage" events, once a day, for every outdoor
plant. The existing deterministic scheduler (rappels.py) then just sees a
recent watering event and naturally skips the task — no weather history
needed at decision time at all.

Tracks the last processed day in SyncMeteo (a single row) so re-running
this on the same day is a no-op for event creation, and re-running after
a gap (e.g. the machine was off for a few days) catches up correctly.
"""

import logging
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from courgette import weather
from courgette.models import Emplacement, Evenement, PlanteJardin, SyncMeteo, TypeEvenement

logger = logging.getLogger(__name__)

# Rainfall (mm) on a given day considered enough to skip a scheduled watering.
AUTO_WATER_RAIN_THRESHOLD_MM = 5.0

FIRST_SYNC_LOOKBACK_DAYS = 15
FORECAST_DAYS_FOR_DECISIONS = 2  # today + tomorrow, i.e. roughly the next 48h


def synchroniser_meteo(session: Session, today: date | None = None) -> list[weather.DailyWeather]:
    """Fetches weather, creates missed automatic watering events, and returns
    the fetched data (so callers can also use today's forecast for the AI
    judgment layer without a second API call).
    """
    today = today or date.today()
    sync = session.get(SyncMeteo, 1)

    if sync is None:
        past_days = FIRST_SYNC_LOOKBACK_DAYS
        logger.info("No previous weather sync found, backfilling %d days.", past_days)
    else:
        gap = (today - sync.derniere_synchro).days
        past_days = max(1, min(gap, FIRST_SYNC_LOOKBACK_DAYS))
        if gap > FIRST_SYNC_LOOKBACK_DAYS:
            logger.warning(
                "Weather sync gap of %d days exceeds backfill window, only backfilling %d days.",
                gap,
                FIRST_SYNC_LOOKBACK_DAYS,
            )

    forecast = weather.get_weather(past_days=past_days, forecast_days=FORECAST_DAYS_FOR_DECISIONS)

    already_synced_through = sync.derniere_synchro if sync else None
    days_to_process = [
        d for d in forecast
        if d.day < today and (already_synced_through is None or d.day > already_synced_through)
    ]

    for day_weather in days_to_process:
        if day_weather.precipitation_mm >= AUTO_WATER_RAIN_THRESHOLD_MM:
            _create_automatic_watering(session, day_weather)
        logger.info(
            "Weather sync processed %s: %.1fmm rain (auto-watering %s).",
            day_weather.day,
            day_weather.precipitation_mm,
            "triggered" if day_weather.precipitation_mm >= AUTO_WATER_RAIN_THRESHOLD_MM else "not triggered",
        )

    last_processed_day = max((d.day for d in days_to_process), default=already_synced_through)
    if last_processed_day is not None:
        if sync is None:
            session.add(SyncMeteo(id=1, derniere_synchro=last_processed_day))
        else:
            sync.derniere_synchro = last_processed_day
            session.add(sync)
        session.commit()

    return forecast


def _create_automatic_watering(session: Session, day_weather: weather.DailyWeather) -> None:
    """Creates an 'arrosage' event for every outdoor plant, for the given day,
    unless one already exists for that plant on that day (idempotent).
    """
    plantes_exterieur = session.exec(
        select(PlanteJardin).where(PlanteJardin.emplacement == Emplacement.EXTERIEUR)
    ).all()

    day_start = datetime.combine(day_weather.day, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    for plante in plantes_exterieur:
        existing = session.exec(
            select(Evenement).where(
                Evenement.plante_jardin_id == plante.id,
                Evenement.type == TypeEvenement.ARROSAGE,
                Evenement.date >= day_start,
                Evenement.date < day_end,
            )
        ).first()
        if existing is not None:
            continue  # already logged (manually or by a previous sync run) for that day

        session.add(
            Evenement(
                plante_jardin_id=plante.id,
                type=TypeEvenement.ARROSAGE,
                date=day_start,
                note=f"Arrosage automatique (pluie {day_weather.precipitation_mm:.1f}mm)",
            )
        )
    session.commit()