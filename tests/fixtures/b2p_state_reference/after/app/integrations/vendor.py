class VendorJob:
    status: str


def mirrors_vendor_wire_state(vendor_job: VendorJob) -> bool:
    return vendor_job.status == "queued"  # noqa: stringly-status: mirrors vendor wire state verbatim
