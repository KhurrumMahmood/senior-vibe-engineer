# C# comment-drift provider

Use this provider only for exact manifest-selected authored `.cs` source. Copy
the sibling `_csharp` provider and enter through
`scripts/analyze_comments_csharp.py`; run it with `--help` for the exact CLI.
It emits `detections.jsonl`, `scan.json`, `findings.json`, and `report.md` under
one named `reports/find-comment-drift/` run directory. The four frozen lexical
bands are legacy-term spelling, source-line-shaped reference, section/banner
form, and imperative narration without a rationale lexeme.

Only Roslyn comment trivia can create a lead. Findings retain the exact
half-open Roslyn `TextSpan` in zero-based UTF-16 code units, comment form,
spelling hash, source hash, and a per-pattern non-claim. Strings, directives,
disabled text, tests, generated/vendor/build/tooling/symlink inputs, malformed
source, and incomplete projects never become production findings. The provider
does not attach prose to a declaration or prove staleness, behavior, runtime
reachability, XML-doc completeness, or refactor safety.

Missing SDK 10.0.302 is `unsupported`; malformed source or project evidence is
`failed`; neither outcome can be reported as clean.
