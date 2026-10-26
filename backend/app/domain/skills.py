"""Skill-label normalisation with a curated alias table (paper Section 4.2).

Matching is deliberately conservative:

1. *exact*   - case/whitespace-insensitive match on a canonical label;
2. *alias*   - case/whitespace-insensitive match on an explicit alias;
3. *compact* - the same after removing spaces, dots, hyphens and underscores
               ("Node JS" -> "nodejs"). Compact keys are checked for collisions
               when the table loads, so this step can never merge two
               canonical skills;
4. otherwise the label is *unrecognised* and kept as written.

There is no fuzzy/edit-distance matching: "React" and "React Native" must
never be merged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Literal

from .models import PROFICIENCY_MAX, PROFICIENCY_MIN, DomainValidationError

DEFAULT_ALIAS_PATH = Path(__file__).with_name("skill_aliases.json")
MAX_SKILL_LABEL_LENGTH = 60

Rule = Literal["exact", "alias", "compact", "unrecognized"]
_COMPACT_STRIP = re.compile(r"[\s.\-_]+")


def _key(label: str) -> str:
    return " ".join(label.split()).casefold()


def _compact(label: str) -> str:
    return _COMPACT_STRIP.sub("", label.casefold())


def clean_label(label: str) -> str:
    return " ".join(label.split())


@dataclass(frozen=True)
class Normalization:
    original: str
    canonical: str
    recognized: bool
    rule: Rule


@dataclass(frozen=True)
class SkillMerge:
    canonical: str
    kept_proficiency: int
    merged_from: tuple[str, ...]


class SkillRegistry:
    def __init__(self, table: dict[str, Iterable[str]]):
        self._canonical: dict[str, str] = {}
        self._alias: dict[str, str] = {}
        self._compact: dict[str, str] = {}
        for canonical, aliases in table.items():
            canonical = clean_label(canonical)
            if not canonical:
                raise DomainValidationError("empty canonical skill label")
            ck = _key(canonical)
            if ck in self._canonical or ck in self._alias:
                raise DomainValidationError(f"canonical label {canonical!r} defined twice")
            self._canonical[ck] = canonical
            for alias in aliases:
                ak = _key(alias)
                owner = self._alias.get(ak) or self._canonical.get(ak)
                if owner and owner != canonical:
                    raise DomainValidationError(f"alias {alias!r} maps to both {owner!r} and {canonical!r}")
                self._alias[ak] = canonical
        for k, canonical in [*self._canonical.items(), *self._alias.items()]:
            ck = _compact(k)
            if not ck:
                continue
            owner = self._compact.get(ck)
            if owner and owner != canonical:
                raise DomainValidationError(
                    f"compact key {ck!r} is ambiguous between {owner!r} and {canonical!r}; add explicit aliases instead"
                )
            self._compact[ck] = canonical

    @classmethod
    def from_file(cls, path: Path = DEFAULT_ALIAS_PATH) -> "SkillRegistry":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data["skills"])

    @property
    def canonical_labels(self) -> list[str]:
        return sorted(self._canonical.values(), key=str.casefold)

    def normalize(self, label: str) -> Normalization:
        cleaned = clean_label(label)
        if not cleaned:
            raise DomainValidationError("empty skill label")
        if len(cleaned) > MAX_SKILL_LABEL_LENGTH:
            raise DomainValidationError(f"skill label longer than {MAX_SKILL_LABEL_LENGTH} characters")
        k = _key(cleaned)
        if k in self._canonical:
            return Normalization(label, self._canonical[k], True, "exact")
        if k in self._alias:
            return Normalization(label, self._alias[k], True, "alias")
        ck = _compact(cleaned)
        if ck in self._compact:
            return Normalization(label, self._compact[ck], True, "compact")
        return Normalization(label, cleaned, False, "unrecognized")

    def normalize_proficiencies(
        self, items: Iterable[tuple[str, int]]
    ) -> tuple[dict[str, int], list[Normalization], list[SkillMerge]]:
        """Normalise (label, proficiency) pairs, merging duplicates and keeping
        the highest stated proficiency. Unrecognised labels that differ only in
        case/whitespace are merged too (the first spelling seen is kept)."""
        out: dict[str, int] = {}
        display_for_key: dict[str, str] = {}
        sources: dict[str, list[str]] = {}
        decisions: list[Normalization] = []
        for label, level in items:
            if not isinstance(level, int) or isinstance(level, bool) or not (
                PROFICIENCY_MIN <= level <= PROFICIENCY_MAX
            ):
                raise DomainValidationError(f"proficiency for {label!r} must be {PROFICIENCY_MIN}-{PROFICIENCY_MAX}")
            n = self.normalize(label)
            decisions.append(n)
            key = _key(n.canonical)
            canonical = display_for_key.setdefault(key, n.canonical)
            out[canonical] = max(out.get(canonical, 0), level)
            sources.setdefault(canonical, []).append(label)
        merges = [
            SkillMerge(c, out[c], tuple(src)) for c, src in sources.items() if len(src) > 1
        ]
        return out, decisions, merges

    def normalize_labels(self, labels: Iterable[str]) -> list[str]:
        seen: dict[str, str] = {}
        for label in labels:
            n = self.normalize(label)
            seen.setdefault(_key(n.canonical), n.canonical)
        return list(seen.values())


@lru_cache(maxsize=1)
def default_registry() -> SkillRegistry:
    return SkillRegistry.from_file()
