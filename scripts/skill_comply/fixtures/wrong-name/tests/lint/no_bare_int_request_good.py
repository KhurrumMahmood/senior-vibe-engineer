"""Known-good fixture for the wrong-name variant.

No allow-listed (`# noqa`) line here on purpose: the rule's emitted tag is drifted
from the wired name, so a noqa keyed to the wired name would not be recognized and
the matcher would fire on it — turning this into a second, unintended defect. Every
line below is legitimately non-firing under the correct POST/GET-scoped matcher, so
GOOD_RC=0 and C3 passes; the only consequential failure is C4 (tag drift blinds
hit-counting).

Covered patterns:

1. ``safe_int(request....get(...))`` — already the canonical form.
2. ``int(x)`` on a non-request value — plain coercion, not user input.
3. ``int(request.headers.get(...))`` — a ``.get`` on a non-POST/GET attr.
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
    # func is safe_int, not int → never fires.
    return safe_int(request.GET.get("qty"), default=1)


def plain_int_is_fine(product_id):
    # Not a request lookup — must not fire.
    return int(product_id)


def non_dict_request_attr_is_fine(request):
    # `.headers.get` is not POST/GET — out of the rule's scope.
    return int(request.headers.get("content-length"))
