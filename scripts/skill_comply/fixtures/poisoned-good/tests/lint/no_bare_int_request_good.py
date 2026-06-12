"""Known-GOOD fixture that is secretly POISONED (skill-comply defect fixture).

A good fixture is supposed to hold ONLY forms the rule must not flag. This one
hides a live anti-pattern — an un-allow-listed ``int(request.POST.get(...))`` —
among the legitimate forms. The rule here is the correct, POST/GET-scoped
matcher, so it FIRES on that line; ``verify_rule`` then sees GOOD_RC=1 (expected
0) and the differential gate (C3) fails.

This is the "the good fixture lies" defect: the proposal's own evidence is
self-contradictory, and C3 catches it with no whole-repo scan needed.
"""
# ruff: noqa
from __future__ import annotations


def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def canonical_form_is_fine(request):
    return safe_int(request.GET.get("qty"), default=1)


def plain_int_is_fine(product_id):
    return int(product_id)


def poison(request):
    # POISON: a live anti-pattern hiding in the "good" fixture, NOT allow-listed.
    # The correct rule fires here → verify_rule GOOD_RC=1 → C3 fails.
    return int(request.POST.get("page"))
