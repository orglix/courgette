"""Garden-wide weather alerts (frost, heatwave) — not tied to a specific plant.

Plain threshold checks on the forecast, same reasoning as smart_todo.py:
no judgment involved, so no LLM here either.
"""

from datetime import date

from courgette import weather

FROST_THRESHOLD_C = 2.0  # minimum temperature at/below which frost is a real risk
HEATWAVE_THRESHOLD_C = 30.0  # maximum temperature at/above which a heatwave alert fires


def get_alerts(today: date | None = None) -> list[dict]:
    """Returns garden-wide alerts for today and the next couple of days.

    Fails safe: if the location isn't configured or the API is unreachable,
    returns an empty list rather than raising — alerts are a bonus, not a
    dependency for the rest of the app.
    """
    today = today or date.today()
    try:
        forecast = weather.get_weather(past_days=0, forecast_days=2)
    except RuntimeError:
        return []

    alerts: list[dict] = []
    for day_weather in forecast:
        if day_weather.day < today:
            continue

        if day_weather.temp_min_c <= FROST_THRESHOLD_C:
            alerts.append(
                {
                    "type": "gel",
                    "date": day_weather.day.isoformat(),
                    "message": (
                        f"Gel possible le {day_weather.day.strftime('%d/%m')} "
                        f"({day_weather.temp_min_c:.1f}°C) — pense à protéger tes plantes sensibles."
                    ),
                }
            )

        if day_weather.temp_max_c >= HEATWAVE_THRESHOLD_C:
            alerts.append(
                {
                    "type": "canicule",
                    "date": day_weather.day.isoformat(),
                    "message": (
                        f"Forte chaleur prévue le {day_weather.day.strftime('%d/%m')} "
                        f"({day_weather.temp_max_c:.1f}°C) — arrose tôt le matin ou tard le soir."
                    ),
                }
            )

    return alerts
