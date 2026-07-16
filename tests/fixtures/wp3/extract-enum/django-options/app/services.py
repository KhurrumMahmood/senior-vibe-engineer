from .models import Ticket


def is_pending(ticket: Ticket) -> bool:
    return ticket.state == "pending"


def start(ticket: Ticket) -> None:
    ticket.state = "running"
