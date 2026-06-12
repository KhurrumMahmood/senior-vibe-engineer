"""Known-good fixture for scripts/lint/no_bare_int_request.py.

Every line here is a legitimate pattern the rule must NOT flag. If the rule
starts flagging anything here it has become too strict.

Covered patterns:

1. ``safe_int(request....get(...))`` — already the canonical form.
2. ``int(x)`` on a non-request value — plain coercion, not user input.
3. ``int(request.headers.get(...))`` — a ``.get`` on a non-POST/GET attr.
4. Allow-listed bare int with a non-empty reason.
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
    # The whole point of the rule: this is what callers should write.
    return safe_int(request.GET.get("qty"), default=1)


def plain_int_is_fine(product_id):
    # Not a request lookup — must not fire.
    return int(product_id)


def non_dict_request_attr_is_fine(request):
    # `.headers.get` is not POST/GET — out of the rule's scope.
    return int(request.headers.get("content-length"))


def allow_listed_is_fine(request):
    # Legitimately bare, suppressed with a reason.
    return int(request.POST.get("trusted"))  # noqa: no-bare-int-request: value validated upstream by the form layer
