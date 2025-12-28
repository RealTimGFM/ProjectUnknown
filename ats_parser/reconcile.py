from __future__ import annotations
from typing import List
from rapidfuzz import fuzz
from .models import ExperienceItem


def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for s in items:
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(s.strip())
    return out


def merge_experience(
    rule_items: List[ExperienceItem], llm_items: List[ExperienceItem]
) -> List[ExperienceItem]:
    if not llm_items:
        return rule_items
    if not rule_items:
        return llm_items
    out: List[ExperienceItem] = []
    used = [False] * len(llm_items)
    for r in rule_items:
        best_i, best = -1, 0
        for i, l in enumerate(llm_items):
            if used[i]:
                continue
            score = 0
            if r.company and l.company:
                score += fuzz.token_set_ratio(r.company, l.company)
            if r.title and l.title:
                score += fuzz.token_set_ratio(r.title, l.title)
            if score > best:
                best = score
                best_i = i
        if best >= 120:
            l = llm_items[best_i]
            used[best_i] = True
            merged = ExperienceItem(
                title=l.title or r.title,
                company=l.company or r.company,
                location=l.location or r.location,
                dates=l.dates if (l.dates.start or l.dates.end) else r.dates,
                bullets=l.bullets or r.bullets,
                technologies=list({*r.technologies, *l.technologies}),
                confidence=max(r.confidence, l.confidence),
            )
            out.append(merged)
        else:
            out.append(r)
    for i, l in enumerate(llm_items):
        if not used[i]:
            out.append(l)
    return out
# ats_parser/reconcile.py

import re
from typing import List
from .models import ExperienceItem

_WS = re.compile(r"\s+")

def _clean_loc(s: str) -> str:
    s = _WS.sub(" ", (s or "").strip())
    s = s.replace(" ,", ",").strip(" ,")
    return s

def postprocess_experience(items: List[ExperienceItem]) -> List[ExperienceItem]:
    """
    Conservative normalization step AFTER extraction/merge:
    - If a company has exactly one known location across extracted items, fill missing locations.
    - Otherwise, only fill from adjacent roles with the same company (common resume layout).
    """
    if not items:
        return items

    # 1) company -> unique location (only if unambiguous)
    comp_to_locs: dict[str, set[str]] = {}
    for it in items:
        comp = (it.company or "").strip()
        loc = _clean_loc(it.location or "")
        if comp and loc:
            comp_to_locs.setdefault(comp.casefold(), set()).add(loc)

    comp_unique_loc = {
        comp: next(iter(locs))
        for comp, locs in comp_to_locs.items()
        if len(locs) == 1
    }

    for it in items:
        if (it.company or "").strip() and not _clean_loc(it.location or ""):
            key = it.company.strip().casefold()
            if key in comp_unique_loc:
                it.location = comp_unique_loc[key]

    # 2) adjacency fallback (only when same company and neighbor has location)
    for i in range(len(items)):
        it = items[i]
        if not (it.company or "").strip():
            continue
        if _clean_loc(it.location or ""):
            continue

        comp_key = it.company.strip().casefold()

        prev_loc = ""
        if i - 1 >= 0 and (items[i - 1].company or "").strip().casefold() == comp_key:
            prev_loc = _clean_loc(items[i - 1].location or "")

        next_loc = ""
        if i + 1 < len(items) and (items[i + 1].company or "").strip().casefold() == comp_key:
            next_loc = _clean_loc(items[i + 1].location or "")

        # Prefer previous role’s location, otherwise next.
        it.location = prev_loc or next_loc or it.location

    # final cleanup pass
    for it in items:
        it.location = _clean_loc(it.location or "")

    return items
