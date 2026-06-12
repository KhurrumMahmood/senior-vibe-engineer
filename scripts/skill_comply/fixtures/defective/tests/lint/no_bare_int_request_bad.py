"""Known-bad fixture for the DEFECTIVE no_bare_int_request rule.

NOTE: this fixture is tailored to the defective rule's (wrong) matcher — it
uses the SUBSCRIPT form ``request.POST[...]``. It makes ``verify_rule.py`` pass
(BAD fires, GOOD clean) even though the rule cannot catch the real ``.get(...)``
anti-pattern. That self-consistency is exactly why the differential verifier
alone is insufficient and the historical-fire check is required.
"""
# ruff: noqa


def post_subscript(request):
    return int(request.POST["page"])


def get_subscript(request):
    return int(request.GET["per_page"])
