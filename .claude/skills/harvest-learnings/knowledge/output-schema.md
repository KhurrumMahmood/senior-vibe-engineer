# The harvest output schema

Every harvested item is one object. The schema is the contract that stops a
harvest from degrading into bare platitudes — the fields it **forces** are
exactly the ones a lazy pass would skip (the exemplar, the back-link, the
portability verdict).

## Per-item shape (`harvest.json` → `items[]`)

```jsonc
{
  "id": "harvest-<kebab>",
  "statement": "the rule, DE-STACKED, in one sentence",
  "source": "extractive | generative",
  "origin_handle": "durable back-link: lint rule name | ADR id | precedent id | known-issue anchor (NOT raw file:line)",

  "exemplar": {                       // REQUIRED — the teeth
    "what_bit": "the specific incident/cost that forged this — concrete, surprising, attributed",
    "host_stack": "the stack it was found in (e.g. Django/Python/crawling)",
    "back_link": "lint:silent-catch | adr:0019 | precedent:<id>"
  },

  "portability": {                    // REQUIRED — earned, not assumed
    "verdict": "ports | stays-home | principle-ports-mechanism-stays",
    "translation_test": "what survived when framework+language+domain were stripped, and what didn't",
    "confidence": "single-constraint-set"   // N=1 default; → validated-across-N when a 2nd project confirms
  },

  "activation": {                     // REQUIRED for a PORTED item — ADR 0020
    "baseline": true
    // OR (instead of baseline):
    // "rungs": [
    //   {"name": "common-sense", "min_maturity": "prototype",  "min_stakes": "internal",          "cost": "cheap"},
    //   {"name": "hardened",     "min_maturity": "production", "min_stakes": "public-adversarial", "cost": "high"}
    // ]
  },

  "detector_hint": "ast | grep | manual"   // OPTIONAL — if it could become a /find-standard-gaps detector
}
```

`exemplar` and `portability` are **required on every item**. `activation` is
required on every **ported** item. An item missing any of these is **not
emittable** — that omission is the exact failure mode this skill exists to
prevent. A `stays-home` item is recorded (project-local value) but is **not**
written as a portable standard.

## The translation test (Stage 3, in detail)

Strip three layers and ask if the rule survives **and still helps**:

1. **Framework** — remove the framework (Django: ORM, views, settings).
2. **Language** — remove the language (Python: the AST, the idioms).
3. **Domain** — remove the domain (crawling / pricing / PIES).

- Survives all three unchanged → **ports** (a general standard).
- Dies at any layer → **stays-home** (record as project-local; still real, just
  not portable).
- The *principle* survives but the *mechanism* is stack-bound →
  **principle-ports-mechanism-stays** (port the de-stacked statement; leave the
  implementation home).

**The filter must bite.** If a whole run produced zero `stays-home` items, you
almost certainly let stack-specific rules through — re-run the test.

## Activation tag (ADR 0020)

Standard activation is **baseline + depth-laddered, two-axis-gated rungs**:

- **`baseline: true`** — always on, every project, every stage. Maintainability /
  consistency (DRY, SOLID, no rampant duplication, universal-not-one-area fixes)
  **plus** the cheap common-sense rung of safety (prompt-injection delimiters,
  input hygiene, no hardcoded secrets, no unauthenticated side-effectful routes).
- **`rungs`** — each heavier rung carries `{min_maturity, min_stakes}` and a
  cost; it activates only when the project meets **both** thresholds. The two
  axes are independent:
  - **maturity:** `prototype` → `first-users` → `production`
  - **stakes:** `internal` → `external` → `public-adversarial`

Many concerns are a **depth ladder**, not on/off: the cheap rung is baseline, the
heavy rung is stakes-gated. Prompt injection: delimiters + parser-strip
(baseline, common-sense) → a second model pre-screening all input (high stakes
only). Tag the ladder, not a single point. Full reasoning in ADR 0020
(`ai-docs/decisions/0020-lifecycle-stakes-standard-activation.md`).

## Worked examples (host-a forge)

| Candidate | Verdict | Activation | Why |
|---|---|---|---|
| `silent-catch` — no bare `except: pass` that swallows | **ports** | baseline | "don't silently swallow errors" survives de-stacking; holds in any language |
| `stringly-status` — state is an enum, not a string | **principle-ports-mechanism-stays** | baseline | typing discipline ports; the `TextChoices` mechanism stays home |
| `safe-dispatch` — risky dispatch through one guarded wrapper | **principle-ports-mechanism-stays** | baseline | "centralize risky dispatch behind one guarded call" ports; the `safe_dispatch` signature is host-a's |
| External-content trust boundary (ADR 0019) | **ports** | baseline (common-sense rung); heavy rung stakes-gated | "treat LLM output + crawled content as untrusted" is general to any crawl+LLM pipeline; second-model screening is a high-stakes rung only |
| `pies-image-dict` — PIES image dict shape | **stays-home** | — | pure domain (autocare PIES); dies at the domain layer |
| "ScraperAPI async batch is unreliable" | **stays-home** | — | vendor-specific operational fact, not a standard |

The two `stays-home` rows are the proof the filter bites. A harvest that emits
either as a portable standard is broken.
