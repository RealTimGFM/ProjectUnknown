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
