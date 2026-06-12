"""Known-bad fixture for scripts/lint/no_bare_int_request.py.

Every ``int(request....get(...))`` here is intentionally an anti-pattern the
rule must flag. ``verify_rule.py`` uses this file as the regression anchor:
if one of these stops firing, the rule has regressed. Do NOT add
``# noqa: no-bare-int-request: ...`` here — the allow-listed case lives in the
sibling ``_good`` fixture.
"""
# ruff: noqa  — this file exists to exercise a custom lint, not pyflakes.


def post_lookup(request):
    # Variant 1: int() of request.POST.get with a single arg.
    return int(request.POST.get("page"))


def get_lookup_with_default(request):
    # Variant 2: int() of request.GET.get with a default arg.
    return int(request.GET.get("per_page", "25"))


def nested_in_expression(request):
    # Variant 3: the int(...) call is a sub-expression — still a violation.
    return int(request.POST.get("offset")) + 1


def self_request_attr(self):
    # Variant 4: works through any object name, not just `request`.
    return int(self.request.GET.get("limit"))
