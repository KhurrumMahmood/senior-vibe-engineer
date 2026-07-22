def render_status_label(status: int) -> str:
    if status >= 500:
        return "server-error"
    return f"status-{status}"
