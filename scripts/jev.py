"""JEV (TypeSafe "System One") pertinence gate for LLM-generated changes.

``daily.py`` calls :func:`is_pertinent` after a DeepSeek change passes the test
suite, to reject a change that stays green but is slop. JEV is a *decision*
model, not a chat model: it takes a ``state`` plus typed questions and returns
calibrated probabilities. A single Noul (yes/no) question scores whether the
change genuinely implements the backlog item.

The gate is opt-in — ``daily.py`` skips it when ``TYPESAFE_API_KEY`` is unset —
and this module is stdlib-only, matching the rest of the repo.

API: ``POST https://api.typesafe.ai/v1/systemone`` (https://docs.typesafe.ai/).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
DEFAULT_THRESHOLD = 0.5

# Retryable statuses per the docs: 408, 429 and 5xx (529 = overloaded).
_RETRYABLE = {408, 429, 529}
_MAX_ATTEMPTS = 4
_BACKOFF = (5, 10, 15)  # seconds — mirrors the SDK's bounded backoff
_MAX_STATE_CHARS = 8000  # keep `state` well under the 32K-token budget


def is_pertinent(slug: str, description: str, diff: str) -> tuple[bool, float]:
    """Return ``(accepted, probability)`` for whether the change is real.

    The Noul question returns ``noul`` in [0, 1]: the model's probability of
    "yes" (a genuine, well-scoped improvement). ``accepted`` is ``noul >=`` the
    configured threshold (default 0.5).
    """
    key = os.environ["TYPESAFE_API_KEY"]
    model = os.environ.get("JEV_MODEL") or DEFAULT_MODEL
    threshold = float(os.environ.get("JEV_THRESHOLD") or DEFAULT_THRESHOLD)

    payload = json.dumps(
        {
            "state": {
                "item": f"{slug}: {description}",
                "diff": diff[:_MAX_STATE_CHARS],
            },
            "model": model,
            "questions": {
                "pertinent": {
                    "type": "noul",
                    "instructions": (
                        "Does this change genuinely implement the backlog item as a "
                        "real, well-scoped, non-trivial improvement to the codebase, "
                        "rather than filler, comment edits, or an unrelated change?"
                    ),
                }
            },
        }
    ).encode("utf-8")

    data = None
    for attempt in range(_MAX_ATTEMPTS):
        req = urllib.request.Request(
            API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRYABLE and attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_BACKOFF[min(attempt, len(_BACKOFF) - 1)])
                continue
            raise RuntimeError(f"JEV HTTP {exc.code}: {exc.read().decode()[:200]}") from exc
        except urllib.error.URLError as exc:
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_BACKOFF[min(attempt, len(_BACKOFF) - 1)])
                continue
            raise RuntimeError(f"JEV connection error: {exc.reason}") from exc
        break

    noul = data["answers"]["pertinent"]["noul"]
    return noul >= threshold, noul
