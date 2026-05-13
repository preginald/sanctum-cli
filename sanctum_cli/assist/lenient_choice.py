"""LenientChoice — a Click Choice that accepts near-miss enum values."""

from __future__ import annotations

import logging
from typing import Any

import click

log = logging.getLogger(__name__)


class LenientChoice(click.Choice):
    """A Click parameter type that normalizes near-miss enum values.

    Accepts a normalize_map dict mapping accepted variants to canonical values.
    When a value is not an exact match, the normalize_map is checked before
    raising a validation error.

    Example::

        LenientChoice(['low', 'normal', 'high', 'critical'], normalize_map={
            'medium': 'normal',
            'urgent': 'critical',
            'enhancement': 'feature',
        })
    """

    def __init__(
        self,
        choices: list[str],
        normalize_map: dict[str, str] | None = None,
        case_sensitive: bool = True,
    ) -> None:
        super().__init__(choices, case_sensitive=case_sensitive)
        self.normalize_map: dict[str, str] = {}
        if normalize_map:
            for variant, canonical in normalize_map.items():
                key = variant if case_sensitive else variant.lower()
                self.normalize_map[key] = canonical

    def convert(
        self, value: str, param: click.Parameter | None, ctx: click.Context | None
    ) -> Any:
        try:
            return super().convert(value, param, ctx)
        except click.BadParameter:
            check = value if self.case_sensitive else value.lower()
            canonical = self.normalize_map.get(check)
            if canonical is not None:
                log.debug(
                    "LenientChoice normalized '%s' -> '%s' for %s",
                    value,
                    canonical,
                    param.name if param else "unknown",
                )
                return super().convert(canonical, param, ctx)
            raise
