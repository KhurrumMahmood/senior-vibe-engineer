# Django binding

Apply these Django/Celery mechanics at the corresponding core phases:

- Use `.venv/bin/python` for Django and `manage.py` commands. The venv guard is
  required only in phases that issue those commands.
- A `TaskRegistrationTest` pins Celery task names and options. Also preserve
  URL names, registered view callables, and imports from both the old module
  and its parent package when a module becomes a package or re-export shim.
- Treat Celery as an external boundary in endpoint matrices. Broker-outage
  findings must call out missing retry behavior, and dormant verification must
  inspect Celery registrations.
- A package `__init__.py` is the natural re-export shim and matches Django's
  module conventions.
