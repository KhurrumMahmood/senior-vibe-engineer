def select_recent_entries(entries):
    return [entry for entry in entries if entry.get("is_recent")]
