from app.models import Site


def nested_lookup(parts, prices):
    out = []
    for part in parts:
        for price in prices:
            if price.part_number == part.number:
                out.append(price)
    return out


def membership_scan(parts, wanted):
    out = []
    for part in parts:
        if part.number in wanted:
            out.append(part)
    return out


def sort_inside_loop(groups):
    out = []
    for group in groups:
        out.append(sorted(group.items))
    return out


def repeated_scan(parts, wanted):
    out = []
    for part in parts:
        out.append(any(row.part_number == part.number for row in wanted))
    return out


def query_inside_loop(site_ids):
    names = []
    for site_id in site_ids:
        site = Site.objects.get(pk=site_id)
        names.append(site.name)
    return names


def high_branch(value):
    total = 0
    if value > 0:
        total += 1
    if value > 1:
        total += 1
    if value > 2:
        total += 1
    if value > 3:
        total += 1
    if value > 4:
        total += 1
    if value > 5:
        total += 1
    if value > 6:
        total += 1
    if value > 7:
        total += 1
    if value > 8:
        total += 1
    if value > 9:
        total += 1
    if value > 10:
        total += 1
    if value > 11:
        total += 1
    if value > 12:
        total += 1
    if value > 13:
        total += 1
    if value > 14:
        total += 1
    if value > 15:
        total += 1
    if value > 16:
        total += 1
    if value > 17:
        total += 1
    return total
