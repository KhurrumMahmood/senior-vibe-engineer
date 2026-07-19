__all__ = ["branchy"]


def branchy(value: int) -> str:
    if value > 0 and value % 2:
        return "odd"
    return "other"


def _private_helper() -> None:
    return None
