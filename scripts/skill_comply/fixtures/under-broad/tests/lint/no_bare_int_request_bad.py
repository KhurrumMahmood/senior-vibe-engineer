"""Known-bad fixture for scripts/lint/no_bare_int_request.py (under-broad).

Every ``int(request....get(...))`` here is intentionally an anti-pattern the
rule must flag. NOTE the self-consistency trap this fixture models: the author
believes the pattern only ever appears on the literal receiver ``request``, so
every variant below uses it — and the rule's narrow matcher passes its own
verifier (C3) while missing the sibling forms (``self.request.POST.get``,
aliased receivers) planted in the seeded repo. Only C9 sees that.
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


def literal_receiver_get(request):
    # Variant 4: another literal-receiver form — GET with no default.
    return int(request.GET.get("cursor"))
