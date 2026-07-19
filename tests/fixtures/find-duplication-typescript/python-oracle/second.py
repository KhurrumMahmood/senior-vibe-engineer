def summarize_pending_entries(entries: list[dict[str, object]]) -> list[str]:
    eligible = [entry for entry in entries if int(entry["retry_count"]) < 3]
    labels = [f'{entry["id"]}:{entry["label"]}' for entry in eligible]
    output: list[str] = []
    for label in labels:
        if label not in output:
            output.append(label)
    return sorted(output)
