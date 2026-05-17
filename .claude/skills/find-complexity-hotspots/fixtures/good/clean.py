from __future__ import annotations


def index_prices(rows):
    by_part = {row.part_number: row for row in rows}
    return [by_part[key] for key in sorted(by_part)]


def summarize(flags):
    allowed = {"active", "pending"}
    return [flag for flag in flags if flag in allowed]
