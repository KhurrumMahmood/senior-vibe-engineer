# sweep digest — engineering-skills (6 findings)

## cx — 6
- `011a6cd88c34` s3 .claude/skills/find-complexity-hotspots/fixtures/bad/hotspots.py::query_inside_loop — `query_inside_loop` calls `Site.objects.get` inside a loop; this may be N+1 ORM work or repeated query shaping.
- … 5 more (see manifest)
