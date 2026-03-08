"""
Utilities for updating a student's notes.yaml rubric from a TAC report.

The notes.yaml file is a grading rubric with manually-filled sections (e.g.
Rapport) alongside auto-gradable sections (e.g. Code).  This module updates
only the auto-gradable items while leaving all other fields untouched.

The blank notes template is driven by a schema — a list of category dicts,
each optionally containing a list of item dicts.  The default schema matches
the PHQ404 rubric, but a fully custom schema can be passed to
:func:`make_notes_template` for a different course or homework structure.

Key→item mapping and rounding are also configurable per-call so the module
can be reused across different courses without modification.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Union

from .report import Report

# ---------------------------------------------------------------------------
# Schema type alias
# ---------------------------------------------------------------------------

# A category entry: {"name": str, "max_points": int|None, "items": [...]}
# An item entry:    {"name": str, "max_points": int|None}
SchemaEntry = Dict  # kept loose — no TypedDict dependency

# ---------------------------------------------------------------------------
# Default rubric schema
# ---------------------------------------------------------------------------

_DEFAULT_SCHEMA: List[SchemaEntry] = [
    {"name": "Total", "max_points": 100},
    {
        "name": "Code",
        "max_points": 60,
        "items": [
            {"name": "Qualité du code (pylint)", "max_points": 30},
            {"name": "Couverture de tests (codecov)", "max_points": None},
            {"name": "Tests publics (pytest)", "max_points": 15},
            {"name": "Tests cachés (pytest)", "max_points": 15},
            {"name": "Documentation, docstrings et typage", "max_points": None},
            {"name": "README, reproductibilité et historique Git", "max_points": None},
        ],
    },
    {
        "name": "Rapport",
        "max_points": 40,
        "items": [
            {"name": "Résumé", "max_points": 3},
            {"name": "Introduction", "max_points": 3},
            {"name": "Théorie", "max_points": 6},
            {"name": "Résultats", "max_points": 6},
            {"name": "Discussion", "max_points": 6},
            {"name": "Conclusion", "max_points": 3},
            {"name": "Références", "max_points": 3},
            {"name": "Vérification des résults", "max_points": 5},
            {"name": "Présentation", "max_points": 5},
        ],
    },
]

# ---------------------------------------------------------------------------
# Default TAC report key → notes.yaml item name mapping
# ---------------------------------------------------------------------------

_DEFAULT_KEY_TO_ITEM: Dict[str, str] = {
    "PEP8": "Qualité du code (pylint)",
    "code_coverage": "Couverture de tests (codecov)",
    "base_tests_passed": "Tests publics (pytest)",
    "hidden_tests_passed": "Tests cachés (pytest)",
}


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def _apply_max_points_overrides(
    schema: List[SchemaEntry],
    overrides: Dict[str, Optional[int]],
) -> List[SchemaEntry]:
    """
    Return a deep copy of *schema* with ``max_points`` values replaced by
    anything present in *overrides*.

    :param schema: Rubric schema (list of category dicts).
    :param overrides: Mapping of item/category name → new max_points value.
    :return: Updated schema (new list of dicts; originals untouched).
    """
    result = []
    for cat in schema:
        cat = dict(cat)
        if cat["name"] in overrides:
            cat["max_points"] = overrides[cat["name"]]
        if "items" in cat:
            new_items = []
            for item in cat["items"]:
                item = dict(item)
                if item["name"] in overrides:
                    item["max_points"] = overrides[item["name"]]
                new_items.append(item)
            cat["items"] = new_items
        result.append(cat)
    return result


def _fmt_points(value: Optional[int]) -> str:
    """Return ``"null"`` or the integer as a string."""
    return "null" if value is None else str(value)


def _render_schema(schema: List[SchemaEntry]) -> str:
    """
    Render a rubric schema as YAML text.

    :param schema: List of category dicts (see :data:`_DEFAULT_SCHEMA`).
    :return: YAML string.
    """
    lines = ["categories:"]
    for cat in schema:
        lines.append(f"  - name: {cat['name']}")
        lines.append(f"    score: null")
        lines.append(f"    max_points: {_fmt_points(cat.get('max_points'))}")
        if "items" in cat:
            lines.append(f"    items:")
            for item in cat["items"]:
                lines.append(f"      - name: {item['name']}")
                lines.append(f"        score: null")
                lines.append(
                    f"        max_points: {_fmt_points(item.get('max_points'))}"
                )
        lines.append("")  # blank line between categories
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public template generator
# ---------------------------------------------------------------------------


def make_notes_template(
    max_points: Optional[Dict[str, Optional[int]]] = None,
    schema: Optional[List[SchemaEntry]] = None,
) -> str:
    """
    Generate a blank notes.yaml template string.

    By default the PHQ404 rubric schema (:data:`_DEFAULT_SCHEMA`) is used.
    Pass a custom *schema* to use a completely different rubric structure.
    Use *max_points* to override individual point values without replacing
    the whole schema.

    :param max_points: Per-item/category ``max_points`` overrides.  Keys must
        match the ``name`` fields in the schema exactly.
    :type max_points: Optional[Dict[str, Optional[int]]]
    :param schema: Full rubric schema.  Each entry is a dict with keys
        ``name``, ``max_points`` (int or None), and optionally ``items``
        (list of ``{"name": ..., "max_points": ...}`` dicts).
        Defaults to :data:`_DEFAULT_SCHEMA`.
    :type schema: Optional[List[dict]]
    :return: YAML text for a blank notes file.
    :rtype: str

    Examples::

        # Default rubric, hidden tests worth 20 pts instead of 15
        tpl = make_notes_template(max_points={"Tests cachés (pytest)": 20})

        # Completely custom rubric
        tpl = make_notes_template(schema=[
            {"name": "Total", "max_points": 100},
            {"name": "Code",  "max_points": 100, "items": [
                {"name": "Tests", "max_points": 50},
                {"name": "Style", "max_points": 50},
            ]},
        ])
    """
    base = schema if schema is not None else _DEFAULT_SCHEMA
    if max_points:
        base = _apply_max_points_overrides(base, max_points)
    return _render_schema(base)


# ---------------------------------------------------------------------------
# YAML update helpers
# ---------------------------------------------------------------------------


def _round_score(value: float, weight: float) -> Union[int, float]:
    """
    Convert a TAC percentage value (0–100) and its weight to an absolute score.

    Scores >= 95 % are snapped to full marks.  Result is rounded to the
    nearest 0.5.

    :param value: Metric percentage score (0–100).
    :param weight: Maximum points for this metric.
    :return: Rounded score as int (if whole) or float.
    """
    if value >= 95.0:
        value = 100.0
    raw = round(value / 100.0 * weight * 2) / 2
    return int(raw) if raw == int(raw) else raw


def _update_item_field(
    yaml_text: str,
    item_name: str,
    field: str,
    new_value: Optional[Union[int, float]],
) -> str:
    """
    Replace a single field (``score`` or ``max_points``) of a named item in
    YAML text.

    :param yaml_text: Raw YAML file content.
    :param item_name: The exact ``name`` value of the item to update.
    :param field: Field name to update (``"score"`` or ``"max_points"``).
    :param new_value: New value, or None to write ``null``.
    :return: Updated YAML text.
    :raises ValueError: If the item or field is not found.
    """
    pattern = re.compile(
        r"(- name: "
        + re.escape(item_name)
        + r"\n(?:\s+\S.*\n)*?\s+"
        + re.escape(field)
        + r": )(null|\S+)",
        re.MULTILINE,
    )
    replacement = r"\g<1>" + ("null" if new_value is None else str(new_value))
    new_text, count = re.subn(pattern, replacement, yaml_text)
    if count == 0:
        raise ValueError(
            f"Field '{field}' of item '{item_name}' not found in notes.yaml"
        )
    return new_text


def _recompute_category_subtotal(
    yaml_text: str,
    category_name: str,
) -> Optional[Union[int, float]]:
    """
    Sum all non-null item scores inside a named category block.

    :param yaml_text: Raw YAML file content (after item scores have been updated).
    :param category_name: The exact ``name`` of the category to sum.
    :return: Summed subtotal, or None if the category is not found.
    """
    cat_match = re.search(
        r"- name: " + re.escape(category_name) + r"\n.*?(?=\n  - name: |\Z)",
        yaml_text,
        re.DOTALL,
    )
    if not cat_match:
        return None
    section = cat_match.group(0)

    # Detect item-level indentation (deeper than the category's own fields)
    item_score_match = re.search(r"^( {4,})score:", section, re.MULTILINE)
    if item_score_match:
        indent = item_score_match.group(1)
        scores = re.findall(
            r"^" + re.escape(indent) + r"score: (\d+\.?\d*)",
            section,
            re.MULTILINE,
        )
    else:
        scores = re.findall(r"^ {4,}score: (\d+\.?\d*)", section, re.MULTILINE)

    total = sum(float(s) for s in scores)
    return int(total) if total == int(total) else round(total, 2)


# ---------------------------------------------------------------------------
# Public update function
# ---------------------------------------------------------------------------


def update_notes_yaml(
    notes_path: Union[str, Path],
    report: "Report",
    max_points: Optional[Dict[str, Optional[int]]] = None,
    schema: Optional[List[SchemaEntry]] = None,
    key_to_item: Optional[Dict[str, str]] = None,
) -> None:
    """
    Update auto-gradable items in a student's notes.yaml from a TAC report.

    For each TAC report key present in *key_to_item*, the corresponding item's
    ``score`` and ``max_points`` are updated in the YAML file.  The subtotal of
    every category that had at least one item updated is then recomputed.
    All other fields are left unchanged.

    If notes.yaml does not exist it is created from a blank template via
    :func:`make_notes_template` (using *schema* and *max_points* if provided).

    :param notes_path: Path to the student's notes.yaml file.
    :param report: TAC Report object from auto-grading.
    :param max_points: Optional per-item ``max_points`` overrides passed to
        :func:`make_notes_template` when the file does not yet exist.
    :type max_points: Optional[Dict[str, Optional[int]]]
    :param schema: Custom rubric schema for template creation.  Defaults to
        :data:`_DEFAULT_SCHEMA`.
    :type schema: Optional[List[dict]]
    :param key_to_item: Mapping from TAC report keys to notes.yaml item names.
        Defaults to :data:`_DEFAULT_KEY_TO_ITEM`.
    :type key_to_item: Optional[Dict[str, str]]
    """
    notes_path = Path(notes_path)
    mapping = key_to_item if key_to_item is not None else _DEFAULT_KEY_TO_ITEM

    if not notes_path.exists():
        notes_path.write_text(make_notes_template(max_points=max_points, schema=schema))

    yaml_text = notes_path.read_text()

    # Track which categories had items updated so we recompute only those
    updated_categories: set = set()

    for tac_key, item_name in mapping.items():
        if tac_key not in report.data:
            continue
        entry = report.data[tac_key]
        value = entry["value"]
        weight = entry["weight"]
        # Keep null for zero-weight (ungraded) metrics
        score = None if weight == 0.0 else _round_score(value, weight)
        max_pts = (
            None
            if weight == 0.0
            else (int(weight) if weight == int(weight) else weight)
        )
        try:
            yaml_text = _update_item_field(yaml_text, item_name, "score", score)
            yaml_text = _update_item_field(yaml_text, item_name, "max_points", max_pts)
        except ValueError:
            continue  # item not present in this student's notes.yaml — skip

        # Find which category this item belongs to in the schema
        active_schema = schema if schema is not None else _DEFAULT_SCHEMA
        for cat in active_schema:
            for it in cat.get("items", []):
                if it["name"] == item_name:
                    updated_categories.add(cat["name"])

    # Recompute subtotals for every category that had items updated
    for cat_name in updated_categories:
        subtotal = _recompute_category_subtotal(yaml_text, cat_name)
        if subtotal is not None:
            yaml_text = re.sub(
                r"(- name: " + re.escape(cat_name) + r"\n\s+score: )(null|\S+)",
                rf"\g<1>{subtotal}",
                yaml_text,
            )

    notes_path.write_text(yaml_text)
