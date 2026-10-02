"""Bounded, deterministic interpretation of project assessment contracts."""

from __future__ import annotations

import re

_AMOUNT_TIERS = re.compile(
    r"Amount:\s*(\d+)\s+points\s+through\s+([\d,]+);\s*"
    r"(\d+)\s+through\s+([\d,]+);\s*"
    r"(\d+)\s+through\s+([\d,]+);\s*otherwise\s+(\d+)",
    re.IGNORECASE,
)


def ordered_amount_tier_interpretation(contract: str) -> str | None:
    """Clarify ordered 'points through' tiers without asking a model to infer bounds."""
    match = _AMOUNT_TIERS.search(contract)
    if match is None:
        return None
    points = [int(match.group(index)) for index in (1, 3, 5, 7)]
    bounds = [int(match.group(index).replace(",", "")) for index in (2, 4, 6)]
    if bounds != sorted(set(bounds)) or any(value < 0 for value in (*points, *bounds)):
        return None
    return (
        f"For amount input 0 through {bounds[0]} inclusive, score {points[0]}; "
        f"greater than {bounds[0]} through {bounds[1]} inclusive, score {points[1]}; "
        f"greater than {bounds[1]} through {bounds[2]} inclusive, score {points[2]}; "
        f"greater than {bounds[2]}, score {points[3]}. "
        f"At exact bounds {bounds[0]}, {bounds[1]}, {bounds[2]}, the scores are "
        f"{points[0]}, {points[1]}, {points[2]} respectively."
    )
