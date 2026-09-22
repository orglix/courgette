"""LLM-based judgment layer for watering decisions.

The deterministic scheduler (rappels.py) decides WHEN a watering task is due.
This module decides whether a due watering task should actually happen TODAY,
given real weather data and general gardening guidance — a judgment call,
not a fixed rule, hence delegated to an LLM rather than hard-coded thresholds.

Uses litellm so the provider/model is swappable via configuration alone
(currently Gemini, could become Claude/OpenAI later without touching this file).
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import litellm

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "gemini/gemini-3.6-flash")
GUIDANCE_PATH = Path(__file__).parent / "knowledge" / "watering_guidance.md"



@dataclass
class WateringDecision:
    plante_jardin_id: int
    keep: bool
    reason: str
 
 
def _load_guidance() -> str:
    return GUIDANCE_PATH.read_text(encoding="utf-8")
 
 
def _build_messages(tasks: list[dict], weather_summary: dict) -> list[dict]:
    system_prompt = (
        "You are a gardening assistant deciding whether scheduled watering tasks "
        "should still happen today, given recent and forecast rainfall. "
        "Follow the guidance below. It gives general judgment, not strict thresholds "
        "to apply mechanically.\n\n"
        f"GUIDANCE:\n{_load_guidance()}\n\n"
        "Answer deterministically and consistently: given the same inputs, always "
        "produce the same decisions — do not introduce creative variation.\n\n"
        "Respond ONLY with a JSON array, no prose, no markdown fences. "
        "Each item must have exactly these fields: "
        '{"plante_jardin_id": <int>, "keep": <bool>, "reason": "<short reason, in French>"}.'
    )
    user_prompt = json.dumps(
        {"weather": weather_summary, "watering_tasks_due": tasks}, ensure_ascii=False
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
 
 
def _strip_markdown_fences(text: str) -> str:
    """Removes ```json ... ``` fences in case the model wraps its output despite instructions."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()[1:]  # drop opening fence (with or without "json")
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
 
 
def decide_watering(
    tasks: list[dict], weather_summary: dict, model: str = DEFAULT_MODEL
) -> list[WateringDecision]:
    """Asks the LLM which of the due watering tasks should be kept today.
 
    `tasks`: list of task dicts as returned by rappels.taches_du_jour(),
    already filtered to type == "arrosage".
    `weather_summary`: dict with at least recent_rainfall_mm and
    rainfall_expected_today_mm (see weather.py).
 
    Raises RuntimeError if the model's response isn't valid JSON in the
    expected shape — callers should decide their own fallback behaviour
    (see smart_todo.py, which falls back to keeping all tasks on failure).
    """
    if not tasks:
        return []
 
    response = litellm.completion(
        model=model,
        messages=_build_messages(tasks, weather_summary),
        num_retries=2,  # transient 5xx errors (e.g. Gemini "high demand") are retried automatically
    )
    content = _strip_markdown_fences(response.choices[0].message.content)
 
    try:
        raw_decisions = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM did not return valid JSON: {content!r}") from exc
 
    try:
        return [
            WateringDecision(
                plante_jardin_id=d["plante_jardin_id"],
                keep=d["keep"],
                reason=d.get("reason", ""),
            )
            for d in raw_decisions
        ]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected JSON shape from LLM: {raw_decisions!r}") from exc
 