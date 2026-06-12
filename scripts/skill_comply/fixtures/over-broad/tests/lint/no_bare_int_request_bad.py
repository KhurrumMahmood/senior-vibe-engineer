"""Known-bad fixture for scripts/lint/no_bare_int_request.py (over-broad variant).

Every ``int(request....get(...))`` here is the target anti-pattern the rule must
flag. ``verify_rule.py`` uses this as the regression anchor. The over-broad rule
fires on all of these too, so the differential gate (C3) passes — the defect is
invisible here and surfaces only at whole-scope C8.
"""
# ruff: noqa  — this file exists to exercise a custom lint, not pyflakes.


def post_lookup(request):
    return int(request.POST.get("page"))


def get_lookup_with_default(request):
    return int(request.GET.get("per_page", "25"))


def nested_in_expression(request):
    return int(request.POST.get("offset")) + 1


def self_request_attr(self):
    return int(self.request.GET.get("limit"))
