---
id: "0035"
namespace: core
title: Cross-repo evidence is frozen as counts-only host attestations; hosts are named only by alias
status: accepted
date: 2026-06-11
deciders: [khurrum, claude-code]
provenance: "Response to a recurring measurement failure: most of this toolkit's real usage evidence was produced in the private originating host and could not port, so honest contracts read none-found and every audit re-discovered a vocabulary gap as a coverage gap."
assumes: ["the toolkit's lifecycle is multi-repo (forged in hosts, extracted to core), so local-only evidence schemas systematically under-report; counts-only summaries are enough signal to distinguish used from never-used"]
revisit_when: ["a second host attestation lands (validates the schema generalizes beyond host-a), or outcome telemetry (ADR 0031's revisit arm) supersedes raw usage counts as the evidence currency, or the alias scheme leaks identity in practice"]
supersedes: []
superseded_by: null
applies_to: [.claude/contracts/provenance/, scripts/host_attest.py, scripts/lint/no_host_references.py]
embodied_by: ["script:scripts/host_attest.py", "contract:.claude/contracts/provenance/attestations.yaml", "contract:.claude/contracts/skills/_schema.yaml", "lint:no_host_references"]
tags: [provenance, evidence, attestation, privacy, obfuscation, cross-repo]
related_smell: null
related_pattern: null
---

# Cross-repo evidence is frozen as counts-only host attestations; hosts are named only by alias

## Context

The contract evidence model implicitly assumed evidence is local:
`run_evidence` counts local scan dirs, `born.commit` points at local git,
`dogfooded_on` wants local runs. But this toolkit's actual lifecycle is
multi-repo — skills are forged and validated in a host adaptation, then
extracted to core. The evidence could not make the jump, so 55 of 73
contracts honestly said `dogfood_kind: none-found` for skills that *were*
used, and every downstream consumer (intent-drift confidence bands, the
effectiveness audit, external review) correctly re-flagged a gap that was
really a *vocabulary* gap. The complaints were not false positives; the
schema lacked a word for "proven upstream."

Separately, the open-source core must not name the private host it came
from. Tracked files carried ~169 mentions of the host's name plus personal
checkout paths, while the host-reference guard covered only four doc
surfaces — about to become permanent on first public push.

## Decision

**1. Host attestations are the carrier for cross-repo evidence.** A
counts-only export (`scripts/host_attest.py`) runs *inside* a host
checkout and emits per-skill usage evidence — invocation counts,
effectiveness-record counts, findings totals, scan-dir counts,
learnings-file presence, first/last dates — plus host-level totals (specs,
plans, ledger records). **No code, no paths, no commit SHAs, no file
contents.** Worktree roots are merged with deduplication (records by
identity, scan dirs by timestamped name), never summed as copies. The
output is committed in core at
`.claude/contracts/provenance/attestations.yaml`, keyed by host alias,
with `attested_by` + `attested_on` carrying the human attestation.

**2. `dogfood_kind: host-attested` is a first-class evidence kind.** A
contract may claim it when the attestation file has a row for the skill;
`dogfooded_on` cites the row (alias + the load-bearing counts). The claim
**caps `provenance_confidence.dogfood` at `med`** until a local re-run
exists — cross-repo evidence is real but not locally reproduced, and the
incentive to re-derive locally must survive.

**3. Hosts are named only by alias.** The public alias (`host-a`,
`host-b`, …) is the only name a host gets anywhere in the tracked tree —
prose, contracts, tasks, fixtures, attestations. The alias→identity
mapping lives **outside this repository**. `scripts/lint/no_host_references.py`
enforces this two-tier: identity tokens (the host's real name, personal
identifiers; stored base64-encoded so the guard is not itself a leak) are
scanned across every tracked file on every commit; structural tokens
(host-proprietary model/route names) are scanned on published doc surfaces
only, so generic lookalikes in synthetic fixtures stay legal.

**4. Attestation is part of harvesting.** Exporting an attestation is part
of distilling a host (`/harvest-learnings` territory): when work in a host
matures or a host is retired, run the export and refresh the row. Future
hosts repeat the same move — the mechanism is the general answer to
"evidence is stranded in the repo where the work happened."

## Alternatives considered

- **Copy raw evidence (logs, scan dirs) into core.** Rejected: leaks host
  content and paths, bloats core with another project's telemetry, and
  duplicates data that remains canonical in the host.
- **Trust prose claims ("ported from the host, used there").** Rejected:
  unverifiable, invisible to tooling, and the exact state that generated
  the recurring complaints.
- **Name the host openly and link its repo.** Rejected: the host is
  private; its name in a public tree is permanent (clones, caches, search
  indexes). The alias costs almost nothing and the mapping stays
  recoverable privately.
- **Hash-based deny list instead of base64 in the guard.** Rejected for
  now: hashes cannot drive the substring/boundary matching the guard
  needs; base64 achieves the stated goal (grep/search-engine obscurity),
  not cryptographic secrecy — stated plainly in the guard's docstring.

## Consequences

- **Easier:** contracts can say something true and checkable about
  upstream usage; the 55 `none-found`s split into honestly-attested vs.
  genuinely-never-used; audits measure real gaps again.
- **Easier:** the next host adoption inherits the mechanism — attestation
  rows accumulate per alias instead of evidence evaporating.
- **Harder:** attestations are snapshots; they staleness-drift as the host
  evolves. Refresh is manual (at harvest time), and `attested_on` makes
  the staleness visible rather than hidden.
- **Harder / honest limit:** counts prove *usage*, not *value*. The
  outcome axis (did findings land and hold) remains ADR 0031/0003
  territory; attestation deliberately does not fake it.
- **Disallowed:** naming a private host by identity anywhere in the
  tracked tree; copying host evidence files into core; summing duplicated
  worktree logs as if independent.

## Verification

- `scripts/host_attest.py` run against the originating host (main checkout
  + 13 worktrees, deduplicated) produced
  `.claude/contracts/provenance/attestations.yaml`: 36 skills with
  evidence, 96 skill-use records, 86 effectiveness records, 271 ledger
  records — zero identity tokens in the output (verified by grep and by
  the tree-wide guard tier).
- The guard runs `always_run` in pre-commit; its identity tier covers
  every tracked file. Its first tree-wide run caught 13 uppercase variants
  a case-sensitive sweep missed.
- `find-skill-intent-drift` accepts the new `dogfood_kind` and validates
  contracts claiming it; the re-bucketing commit keeps the scan green.
