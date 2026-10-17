"""DeepSeek-backed implementation of backlog items that lack a handler.

Used by ``daily.py`` when the next undone item has no deterministic handler and
``DEEPSEEK_API_KEY`` is set. The model receives the item description plus a
scoped view of the sources — the manifest, the README, and the modules/tests
named by the item — and returns the full new content of only the files it
changes. The change is committed only if the test suite stays green and the
local scope gate passes.

Scoping keeps cost and latency down while making sure the model can see the
file it is asked to edit (the old fixed list omitted ``report.py``,
``pooling.py``, ``bootstrap.py``, ``ascii_plot.py`` and ``README.md``).

The API is OpenAI-compatible, so swapping to another provider later is a
one-line ``API_URL`` / model change.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-flash"
MAX_TOKENS = 32000
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}

BASE_FILES = [
    "main.py",
    "stability_shelf_life/__init__.py",
    "README.md",
    "requirements.txt",
]

MODULE_FILES = {
    "model": ["stability_shelf_life/model.py", "tests/test_model.py"],
    "io": ["stability_shelf_life/io.py", "tests/test_io.py"],
    "report": ["stability_shelf_life/report.py", "tests/test_report.py"],
    "pooling": ["stability_shelf_life/pooling.py", "tests/test_pooling.py"],
    "bootstrap": ["stability_shelf_life/bootstrap.py", "tests/test_bootstrap.py"],
    "ascii_plot": ["stability_shelf_life/ascii_plot.py", "tests/test_ascii_plot.py"],
    "cli": ["tests/test_cli.py", "tests/test_cli_out.py"],
}

# Item vocabulary -> module that owns the code.
MODULE_ALIASES = {
    "residual": "model",
    "outlier": "model",
    "diagnostic": "model",
    "arrhenius": "model",
    "kinetic": "model",
    "confidence": "model",
    "band": "ascii_plot",
    "plot": "ascii_plot",
    "chart": "ascii_plot",
    "pool": "pooling",
    "batch": "pooling",
    "report": "report",
    "markdown": "report",
    "csv": "report",
    "html": "report",
    "audit": "report",
    "provenance": "report",
}

SYSTEM_PROMPT = (
    "You are an expert Python developer maintaining `stability-shelf-life`, a "
    "pure-stdlib tool for pharmaceutical stability modelling (ICH Q1E + "
    "Arrhenius). Implement exactly ONE well-scoped backlog item.\n"
    "Rules:\n"
    "- Make a MINIMAL, correct change; touch 1-3 files at most.\n"
    "- If you change production code, add or update a test that covers it.\n"
    "- Do NOT break existing behaviour; the existing test suite must keep passing.\n"
    "- NEVER modify or create files under .github/workflows/ — pushes touching\n"
    "  workflow files are rejected by GitHub and the change will be discarded.\n"
    "- Follow the existing style: stdlib only, type hints, frozen dataclasses.\n"
    "- Return ONLY a JSON object, with this exact shape and no surrounding prose:\n"
    '  {"summary": "<conventional commit subject>", "patch": "<unified diff>"}\n'
    '- "patch" must be a valid git unified diff that applies with `git apply`:\n'
    "  include `diff --git a/<path> b/<path>`, `--- a/<path>`, `+++ b/<path>`\n"
    "  and `@@` hunks, and use `/dev/null` for a new file. Send ONLY the changed\n"
    "  lines plus a few lines of context — never the whole file.\n"
    "- You MUST change at least one file. There is no 'already satisfied' answer.\n"
    "  If the item is genuinely impossible, return an empty patch with an\n"
    "  explanation; the run treats that as a failure."
)


def _propose_prompt(count: int) -> str:
    return (
        "You are the maintainer of `stability-shelf-life`, a pure-stdlib tool for "
        "pharmaceutical stability modelling (ICH Q1E + Arrhenius). Propose NEW "
        "backlog items that would genuinely improve it for GMP/ICH use.\n"
        "Requirements:\n"
        f"- Propose {count} items, each concrete and implementable in ONE focused change.\n"
        "- Do NOT duplicate anything already in the backlog, the proposed file, or the code.\n"
        "- No trivial filler (comment edits, renames, cosmetic tweaks).\n"
        "- Slugs are kebab-case.\n"
        "- Each title MUST include: `Acceptance: <testable criterion>. "
        "Demo: `<command>`. Files: <comma-separated paths, max 3>`.\n"
        '- Return ONLY JSON: {"items": [{"slug": "...", "title": "...", "why": "..."}]}'
    )


def _gather_context(slug: str, description: str) -> str:
    """Manifest + README + the modules and tests named by the item."""
    key = re.sub(r"[^a-z0-9]", "", (slug + " " + description).lower())
    selected = list(BASE_FILES)
    names = {name for name in MODULE_FILES if name.replace("_", "") in key}
    for token, name in MODULE_ALIASES.items():
        if token in key:
            names.add(name)
    if names:
        for name in names:
            selected.extend(MODULE_FILES[name])
    else:
        for files in MODULE_FILES.values():
            selected.extend(files)

    parts = []
    seen = set()
    for rel in selected:
        if rel in seen:
            continue
        seen.add(rel)
        path = ROOT / rel
        if path.exists():
            parts.append(f"### {rel}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def _call(messages) -> str:
    key = os.environ["DEEPSEEK_API_KEY"]
    model = os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": MAX_TOKENS,
            "reasoning_effort": "low",
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    last_error = None
    for attempt in range(4):
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
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            if not content:
                print(
                    "DeepSeek returned empty content: "
                    f"finish_reason={choice.get('finish_reason')} "
                    f"reasoning={bool(choice['message'].get('reasoning_content'))} "
                    f"usage={data.get('usage')}"
                )
            return content
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()[:300]
            last_error = f"DeepSeek HTTP {exc.code}: {body}"
            if exc.code in _RETRY_STATUS and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(last_error) from exc
        except urllib.error.URLError as exc:
            last_error = f"DeepSeek connection error: {exc.reason}"
            if attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(last_error) from exc
    raise RuntimeError(last_error or "DeepSeek call failed")


def _extract_json(content: str) -> dict:
    """Parse the JSON object DeepSeek returned.

    Despite ``response_format: json_object`` the model sometimes wraps the
    object in a markdown fence or appends trailing prose / a second object,
    which breaks a naive ``json.loads``. Parse the *first* complete JSON object
    and ignore anything around or after it.
    """
    text = content.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(obj, dict):
            return obj
    start = text.find("{")
    if start == -1:
        raise RuntimeError(f"DeepSeek returned no JSON object: {content[:200]!r}")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise RuntimeError(f"DeepSeek returned a non-object JSON value: {content[:200]!r}")
    return obj


def _run(cmd):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)


def _patch_files(patch: str) -> List[Tuple[str, bool]]:
    """Return ``(path, existed)`` for every file header in a unified diff."""
    written: List[Tuple[str, bool]] = []
    existed = True
    for line in patch.splitlines():
        if line.startswith("--- "):
            existed = line[4:].strip() != "/dev/null"
        elif line.startswith("+++ "):
            target = line[4:].strip()
            if target == "/dev/null":
                raise RuntimeError("refusing a patch that deletes a file")
            rel = target[2:] if target.startswith("b/") else target
            if rel.startswith("/") or ".." in Path(rel).parts:
                raise RuntimeError(f"refusing unsafe path in patch: {rel}")
            if rel not in [p for p, _ in written]:
                written.append((rel, existed))
    if not written:
        raise RuntimeError("patch contains no file headers")
    return written


def _apply_patch(patch: str) -> List[Tuple[str, bool]]:
    """Validate and apply a unified diff; return the files it touched."""
    if not patch.strip():
        return []
    if not patch.lstrip().startswith(("diff --git", "--- ")):
        raise RuntimeError("response is not a unified diff")
    files = _patch_files(patch)
    handle = tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False)
    try:
        handle.write(patch if patch.endswith("\n") else patch + "\n")
        handle.close()
        check = _run(["git", "apply", "--check", "--whitespace=nowarn", handle.name])
        if check.returncode != 0:
            raise RuntimeError(f"patch does not apply: {check.stderr.strip()[:500]}")
        applied = _run(["git", "apply", "--whitespace=nowarn", handle.name])
        if applied.returncode != 0:
            raise RuntimeError(f"git apply failed: {applied.stderr.strip()[:500]}")
    finally:
        os.unlink(handle.name)
    return files


def implement(slug: str, description: str, feedback: str | None = None) -> Tuple[str, List[Tuple[str, bool]]]:
    """Implement one item via DeepSeek.

    Returns ``(commit_subject, written)`` where ``written`` is a list of
    ``(relative_path, existed_before)`` tuples so the caller can revert.
    """
    context = _gather_context(slug, description)
    user = (
        f"Backlog item `{slug}`: {description}\n\n"
        f"Current repository files:\n\n{context}"
    )
    if feedback:
        user += (
            "\n\nYour previous attempt failed (tests, scope gate or patch "
            "application). Here is the output — fix it and return the corrected JSON:\n\n"
            + feedback
        )

    content = _call(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]
    )
    result = _extract_json(content)
    patch = result.get("patch") or ""
    summary = result.get("summary") or f"feat: {slug}"
    if not patch.strip():
        return summary, []
    written = _apply_patch(patch)
    return summary, written


def propose_items(count: int = 10):
    """Ask DeepSeek for ``count`` new backlog items, as (slug, title, why)."""
    context = _gather_context("", "")
    backlog = (ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    proposed_path = ROOT / "BACKLOG.proposed.md"
    proposed = proposed_path.read_text(encoding="utf-8") if proposed_path.exists() else ""
    user = (
        "Current repository files:\n\n" + context
        + "\n\nCurrent backlog (do not duplicate):\n\n" + backlog
        + "\n\nAlready proposed (do not duplicate):\n\n" + proposed
    )
    content = _call(
        [
            {"role": "system", "content": _propose_prompt(count)},
            {"role": "user", "content": user},
        ]
    )
    data = _extract_json(content)
    items = data.get("items") or []
    return [(it["slug"], it["title"], it.get("why", "")) for it in items]
