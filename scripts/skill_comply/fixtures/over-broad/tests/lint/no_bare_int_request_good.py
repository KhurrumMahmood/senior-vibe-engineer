"""Known-good fixture for scripts/lint/no_bare_int_request.py (over-broad variant).

Only forms the rule must NOT flag: ``safe_int(...)``, plain ``int(non-get)``, and
an allow-listed bare int. Deliberately OMITS ``int(request.headers.get(...))`` /
``int(request.session.get(...))`` — under the over-broad matcher those WOULD
fire, and a good fixture that fires would trip ``verify_rule`` (C3). The whole
point of this fixture is that the over-broad defect passes C3 and is caught only
by the scorer's whole-scope C8.
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
    # The canonical form — func is safe_int, not int → never fires.
    return safe_int(request.GET.get("qty"), default=1)


def plain_int_is_fine(product_id):
    # Not a .get() argument → never fires.
    return int(product_id)


def allow_listed_is_fine(request):
    # Legitimately bare, suppressed with a reason.
    return int(request.POST.get("trusted"))  # noqa: no-bare-int-request: validated upstream by the form layer
