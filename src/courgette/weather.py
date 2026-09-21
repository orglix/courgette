"""Weather client using the Open-Meteo API (free, no API key required).

Fetches recent rainfall and the short-term forecast for a fixed location.
Single garden for now: the location is read from environment variables.
If we ever support multiple gardens/locations, this is the module that
would need a location parameter instead of reading from the environment.
"""

import os
from dataclasses import dataclass
from datetime import date

import httpx

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class DailyWeather:
    day: date
    precipitation_mm: float
    temp_min_c: float
    temp_max_c: float


def _get_location() -> tuple[float, float]:
    """Reads LATITUDE/LONGITUDE from the environment.

    Raises a clear error if missing, same pattern as db.py's DATABASE_URL check.
    """
    lat = os.environ.get("LATITUDE")
    lon = os.environ.get("LONGITUDE")
    if not lat or not lon:
        raise RuntimeError(
            "LATITUDE/LONGITUDE missing. Add them to .env "
            "(e.g. LATITUDE=50.63 LONGITUDE=3.01 for the Lille area)."
        )
    return float(lat), float(lon)


def get_weather(past_days: int = 2, forecast_days: int = 3) -> list[DailyWeather]:
    """Returns daily weather from `past_days` days ago through `forecast_days` days ahead."""
    lat, lon = _get_location()
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum,temperature_2m_min,temperature_2m_max",
        "past_days": past_days,
        "forecast_days": forecast_days,
        "timezone": "auto",
    }
    response = httpx.get(OPEN_METEO_URL, params=params, timeout=10)
    response.raise_for_status()
    daily = response.json()["daily"]

    return [
        DailyWeather(
            day=date.fromisoformat(daily["time"][i]),
            precipitation_mm=daily["precipitation_sum"][i],
            temp_min_c=daily["temperature_2m_min"][i],
            temp_max_c=daily["temperature_2m_max"][i],
        )
        for i in range(len(daily["time"]))
    ]


def recent_rainfall_mm(weather: list[DailyWeather], today: date) -> float:
    """Total rainfall (mm) over the days strictly before today."""
    return sum(d.precipitation_mm for d in weather if d.day < today)


def rainfall_expected_today_mm(weather: list[DailyWeather], today: date) -> float:
    """Rainfall (mm) forecast for today. 0.0 if today is not in the dataset."""
    return next((d.precipitation_mm for d in weather if d.day == today), 0.0)
