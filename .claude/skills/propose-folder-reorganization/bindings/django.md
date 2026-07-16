# Django binding

- A Django app boundary is a framework floor alongside Python package
  semantics and test-runner discovery.
- The inspection helper is stdlib-only and does not import Django.
- Under `core/management/commands/`, command discovery is filename-based.
  Moving a command below another package breaks `manage.py <command_name>`;
  emit `defer_framework_convention` unless the proposal explicitly preserves
  that public runner contract.
