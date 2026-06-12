"""Known-good fixture for the DEFECTIVE no_bare_int_request rule.

Legitimate patterns the rule must not flag. (The defect is in coverage, not in
false positives, so this fixture is genuinely clean under the rule.)
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
    return safe_int(request.GET["qty"])


def plain_int_is_fine(product_id):
    return int(product_id)


def allow_listed_is_fine(request):
    return int(request.POST["trusted"])  # noqa: no-bare-int-request: value validated upstream
