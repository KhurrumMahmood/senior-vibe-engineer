#!/usr/bin/env python3
"""Standalone child-process entry point for parser-backed sweep providers."""
from __future__ import annotations

import builtins
import socket
import sys
import urllib.request
from pathlib import Path
from typing import NoReturn


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

class DetectionIsolationError(RuntimeError):
    """A parser detector attempted a forbidden network/model operation."""


def _forbidden_network(*_args: object, **_kwargs: object) -> NoReturn:
    raise DetectionIsolationError("parser-backed detection cannot access the network")


def install_detection_isolation() -> None:
    """Deny network access and model-provider imports inside the detector child."""
    socket.getaddrinfo = _forbidden_network
    socket.getnameinfo = _forbidden_network
    socket.socket.connect = _forbidden_network
    socket.socket.connect_ex = _forbidden_network
    socket.socket.sendto = _forbidden_network
    if hasattr(socket.socket, "sendmsg"):
        socket.socket.sendmsg = _forbidden_network
    socket.gethostbyname = _forbidden_network
    socket.gethostbyname_ex = _forbidden_network
    socket.gethostbyaddr = _forbidden_network
    urllib.request.urlopen = _forbidden_network
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_: object = None,
        locals_: object = None,
        fromlist: object = (),
        level: int = 0,
    ) -> object:
        if name.split(".", 1)[0] in {"anthropic", "openai"}:
            raise DetectionIsolationError(
                "parser-backed detection cannot import a model provider"
            )
        return original_import(name, globals_, locals_, fromlist, level)

    builtins.__import__ = guarded_import


def main() -> int:
    """Install the isolation boundary before importing any detector runtime."""
    install_detection_isolation()
    from sweep.ecosystem import provider_process_main

    return provider_process_main()


if __name__ == "__main__":
    raise SystemExit(main())
