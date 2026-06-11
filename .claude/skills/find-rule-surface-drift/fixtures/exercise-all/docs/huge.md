# Huge

A registered, referenced doc that exceeds the per-doc soft budget. The
fixture run uses --max-doc-chars=200; this file deliberately sits above
that threshold so the `oversized_doc` band fires. It is mentioned in
`notes.md` and so should NOT also fire `unreferenced_doc`. Padding to
push past 200 chars: lorem ipsum dolor sit amet, consectetur adipiscing.
