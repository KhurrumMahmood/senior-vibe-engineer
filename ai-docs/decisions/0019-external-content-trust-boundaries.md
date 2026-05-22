---
id: "0019"
title: External Content Trust Boundaries
status: proposed
date: 2026-05-21
deciders: []
supersedes: []
superseded_by: null
applies_to: []
tags: [security, prompt-injection, code-execution, llm, trust-boundary, crawled-content, ai-runtime]
related_smell: null
related_pattern: null
---

# External Content Trust Boundaries

## Context

AI-assisted products introduce trust boundaries the classic web-security model
doesn't name. Two are acute in the host project (pnci-pricing) and general to
any crawl+LLM pipeline:

- **Crawled third-party HTML flows into LLM prompts.** Pages the operator does
  not control become part of the model's context — indirect prompt injection.
- **The LLM emits code that is executed.** `extraction_code` and
  `post_processing_code` are LLM-generated Python that is compiled and `exec()`'d
  in the worker process.

The 2026-05-21 LLM-trust-boundary audit found this is under-guarded: eight
`exec()` sites with no import restriction (confirmed empirically that
`exec(code, {}, {})` does **not** block `import os` / `import subprocess`); the
one strong control (`ppc_code_is_safe`, an AST import-allowlist) is enforced only
inside the Site Intelligence adapter and **bypassed at two DB write boundaries**
(`apply_extraction_result`, `FieldChatSuggestionService._build_defaults`); the
save-boundary check is syntax-only and accepts any valid Python; and HTML
excerpts reach prompts as plain JSON strings with only a natural-language "this
is untrusted" warning as the boundary.

The question: how should the ecosystem model "content from outside the trust
boundary" — crawled HTML, third-party API responses, **and** LLM output?

## Decision

Treat **LLM output and crawled/third-party content as untrusted input**, subject
to the same boundary discipline as raw user input: validate or encode at the
boundary, and re-validate at **every** persistence boundary — not only at
generation time. Concretely:

1. **LLM-generated code is untrusted until AST-allowlist-checked _and_ executed
   in a restricted/isolated runtime.** A syntax check is not a safety check. The
   safety check (AST import-allowlist or equivalent) must run at the **DB write
   boundary**, so a direct write that skips the generating pipeline cannot land
   unchecked code. Open `exec()` of stored code is a standing liability even with
   the AST check, so the runtime itself should move toward restriction/isolation.
2. **Crawled/third-party content embedded in prompts is structurally delimited**
   (sentinel / XML boundary the model is told never to cross), **parser-stripped
   not regex-stripped**, and never trusted to carry instructions. The
   natural-language warning stays, but as defense-in-depth, not the only barrier.
3. **These boundaries are declared, not folklore.** They live as the
   `manual` standard `idea-untrusted-content-boundary` in `find-standard-gaps`
   and are governed by this ADR because they are architectural.

## Alternatives considered

- **Trust LLM output because we wrote the prompt.** Rejected: with indirect
  injection, the effective author of the output can be a hostile crawled page,
  not the operator.
- **Syntax-check generated code and call it safe.** Rejected empirically:
  `exec({}, {})` resolves imports through `sys.modules`; valid Python imports
  `os`/`subprocess` freely.
- **Rely on the natural-language "untrusted source data" warning alone.**
  Rejected as the *sole* control: that is a model-capability bet, not a
  structural guarantee. Keep it; add delimiters + output validation around it.
- **Heavyweight sandbox per exec (separate microservice / container).** Deferred,
  not rejected: subprocess isolation / RestrictedPython / gVisor is the right
  long-term answer for code execution (tracked as AR-9 in the host project), but
  the immediate cheap win is closing the AST-check bypass at the write boundary.
  This ADR names the boundary *principle*; the sandbox *mechanism* is a separate
  decision.

## Consequences

- **Easier:** one named principle covers user input, crawled content, and LLM
  output — fewer ad-hoc special cases, and a single place (`apply` / save
  boundaries) to enforce.
- **Harder:** every generate → persist → execute path needs a re-validation step;
  prompt assembly needs delimiter discipline; the AST allowlist for full
  `extraction_code` is broader than for PPC (must permit `from bs4 import
  BeautifulSoup`) and needs its own design.
- **Now disallowed:** writing `post_processing_code` / `extraction_code` to the DB
  without the safety check; embedding raw HTML in a prompt without a structural
  boundary.

## Verification

- The AST safety check is enforced at **all** `FieldExtractionConfig` /
  `SiteConfiguration` code-write boundaries, not just the SI adapter.
- A regression test proves a malicious-import PPC posted to the apply endpoint is
  rejected before it reaches the DB (`/prevent-regression` candidate).
- HTML-excerpt prompt assembly wraps content in a sentinel block and uses a
  parser-based strip; a fixture proves a `<script>`-evasion payload is removed.
- The `manual` standard `idea-untrusted-content-boundary` tracks coverage; the
  review-avatar `security-risk-engineer` lane checks it.
- **This ADR is `proposed`** until (a) the write-boundary safety check lands and
  (b) the `exec()` sandboxing mechanism (AR-9) is decided in its own ADR. This
  one establishes the principle; it does not by itself close the RCE.
