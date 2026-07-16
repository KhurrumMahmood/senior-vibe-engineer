# WP3 Slice 4 deterministic evidence

This generated report supersedes every earlier Slice 4 evidence claim.
Its hashes and counts are reconstructed and checked by `wp3_slice4_replay.py`.

## Git and runtime binding

- Implementation revision: `8eb940755a43c564de6963f2470c6eaaca8adc4b`
- Implementation tree: `dfe38bb28cb1e8d381733ed5d9c0a971757e521b`
- Evidence relationship: only `reports/portable-skill-ecosystem-completion/WP3/slice-4-evidence.md, reports/portable-skill-ecosystem-completion/WP3/slice-4-repair-command-manifest.json, reports/portable-skill-ecosystem-completion/WP3/slice-4-repair-command-manifest.sha256` may change afterward.
- Python argv token: `{python-interpreter}`
- Python version-output SHA-256: `ba6a5822d759e42f87b9f8c330342a61fefded3301f7d29a5b2e2e2f0cb59908`
- Collected tests: `693`

## Command evidence

| Command | Exit | stdout+stderr SHA-256 |
|---|---:|---|
| `python-version` | 0 | `ba6a5822d759e42f87b9f8c330342a61fefded3301f7d29a5b2e2e2f0cb59908` |
| `pytest-version` | 0 | `e143bc467f4d4f6fb89158f8b30f8849791aa5a5f25cca52c735880897645518` |
| `ruff-version` | 0 | `2a3425f22c174c88347315880601aedb0dc1fc81941a5b9a208bb55c55353f69` |
| `focused-repair` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `full-suite` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `ruff-changed` | 0 | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `skill-meta` | 0 | `2badb5016d4f1cd99837de4e36bf24f4756cbbccdf13151085c26ee54427bb6b` |
| `core-leakage` | 0 | `6df16c0b74d1f968af620b51b591d947d64f292fd9a2694388ee10fcd95d245a` |
| `artifact-drift` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `spec-inventory` | 0 | `9f0a04ef0e2ade22f09025cb2f92bb983d5329e12752435aa9d180e975864965` |
| `binding-selection-evidence` | 0 | `1df34ba88f33fbae31f1caa7eabe600916f7c8c72657479d0d6d1dfc97591e41` |
| `python-fixture` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `python-collect` | 0 | `6261e8515902d06c0f326f44aa84d1b33981a712bec0153cd16a843cd1e9595b` |
| `python-render` | 0 | `15bf230418b20f71eff644eded923f8fb8bc8d9c94675a29615decb3f0080336` |
| `python-render-exec` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `django-collect` | 0 | `60918bb3144aed2400232acffc6e5783d5e5babb4ccd1f645a5d0a46c572a0f0` |
| `django-render-oracle` | 0 | `ecbfec3d962b5d62153342610e5dc0ee02284a70cf6ced593474df1fe88695fa` |

## Binding-selection evidence

- Profile SHA-256: `fb73e3ed13f95dde159296e8728afd1e4d4a0b977f8b6c26a0bfa012c2318f1a`
- Core SHA-256: `733f71315fb0c00c2ee271c41f01c52ec958bbee1d9061abb4473b74ff6f9334`
- Binding SHA-256 map: `{"django": "78f51810be915177deaa547db435db51f0319ce21da6fdd87ec9c8601d21a3cd", "python": "da37eb198376ef5a1fda9e8d4819f21f26d675cab93950c5a2c1d83aa5941050"}`
- Rendered SHA-256: `6bc3c11f3c16df1243a4d81a6b8192dbaa9f28e4162563e011229d9482ffa488`
- Negative outcomes: `ambiguity`, `incompatibility`, and `zero_match` all rejected.
- Cross-root binding leak: `false`.
- Order-independent: `true`.

## Replay artifacts

| Path | Bytes | SHA-256 |
|---|---:|---|
| `binding-selection/evidence.json` | 3696 | `39227e363d182515c7bf0d9b52be91da408346fb10b6b610429851966ae79fc2` |
| `django/normalization.json` | 194 | `52291b6e0c9c5ab96bfaa7c02b4d87f33da74cddda1282f51d2f2b684128b7f3` |
| `django/proposal.md` | 2451 | `b72e1b98ca26f4ee903f3997667d944aad1668552f53377b26782219f3b9702a` |
| `django/scope.json` | 117 | `703c326ab3e967711d779fdff7e154875f48d5df8825f458b39ced91e95d4fd1` |
| `django/semantic.json` | 2417 | `b9adf1cb0ff337d645f4de897e1b5fae21c668ba0e1a680b986d1881f3fc783e` |
| `django/targets.json` | 2095 | `6fda10ce52e087fd96c7618f30920c42fee833584dba741b0b63c0eec21119c7` |
| `python/job_status.py` | 101 | `2bfab791f87055ec22729feeb8f1fb0a3d3d8a316f4205f5ea4770a60886507c` |
| `python/scope.json` | 89 | `983987ce3155bd6f6f4fba2de03b4fda286ea58be45a05db050a3376c0b8a55d` |
| `python/semantic.json` | 1288 | `fe28e6d8b7f8ad6e0249351e103344f282b8c031a91d6329b19165221ee472ce` |
| `python/targets.json` | 2265 | `44422f5c570d074b2864a8f47cc84dcb879fd4d26dbadbf0133c151182cb210b` |

## Principal implementation sources

| Path | Bytes | SHA-256 |
|---|---:|---|
| `scripts/_lib/binding_loader.py` | 13013 | `cabfc908b8f95856b46fb59c2bfe219e542b265c8dc6e0e12bbd06579a47a13e` |
| `.claude/skills/extract-enum/SKILL.md` | 8613 | `733f71315fb0c00c2ee271c41f01c52ec958bbee1d9061abb4473b74ff6f9334` |
| `.claude/skills/extract-enum/bindings/python.md` | 2195 | `da37eb198376ef5a1fda9e8d4819f21f26d675cab93950c5a2c1d83aa5941050` |
| `.claude/skills/extract-enum/bindings/django.md` | 1864 | `78f51810be915177deaa547db435db51f0319ce21da6fdd87ec9c8601d21a3cd` |
| `.claude/skills/extract-enum/scripts/collect.py` | 44896 | `513d36ba6a1046f13a5d2c10f6d84d4e7e8bd8c38687e0a329172aafab756649` |
| `.claude/skills/extract-enum/scripts/propose.py` | 18361 | `2daa93f133dbe78a4abebb92ea92c38ac70755dbf839951468cefdbc22f4918b` |
| `.claude/skills/extract-enum/scripts/propose_python.py` | 6854 | `bfe8f31f3a06fa821f5de63fe0db860f2c06024698abe4d271f361bd3a56dbad` |
| `scripts/wp3_binding_selection_evidence.py` | 9773 | `993254a3fab5e10736d9e88466ed5ecc6428aff543c1479280218864b93bb5cf` |
| `scripts/wp3_slice4_replay.py` | 26296 | `070c6f725b6191d2fb9f974ec5e91b58d001a68affe3d22c7d47fd9bb0152b43` |
| `tests/test_binding_loader.py` | 9522 | `c96d574b2e4476fadcfbcb61fb1ede90e6392076d4bb5916e5d0993523d38a77` |
| `tests/test_extract_enum_binding.py` | 16654 | `cac3882b67b0753cc0666fb6770ed87fc3f984e783085091a48748404a0b86a0` |
| `tests/test_wp3_slice4_replay.py` | 10737 | `6562c3b1e3581bd187000126bbeb60e901b5ed0ea72f7e5a598f0e4dbcca1e25` |
| `tests/fixtures/wp3/extract-enum/ar7-semantic-oracle.json` | 1979 | `9d5caa6999d34d1f3270b8bd41da6a33d9e4ecf4c6da904fcaca5f581a11c41d` |
