def summarize_test_entries(entries):
    normalized = []
    for entry in entries:
        label = entry["label"].strip()
        if not label:
            continue
        normalized.append({"id": entry["id"], "label": label})
    normalized.sort(key=lambda item: item["label"])
    return normalized
