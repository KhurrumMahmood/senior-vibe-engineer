"""Strict bounded subprocess capture shared by sweep providers."""
from __future__ import annotations

import hashlib
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CapturedProcess:
    """A process result whose combined retained artifacts never exceed limit + 1."""

    returncode: int
    timed_out: bool
    output_overflow: bool
    raw: Mapping[str, Any]
    stdout: bytes
    stderr: bytes

    @property
    def code(self) -> int:
        """Return the shell-style code expected by the native provider lane."""
        return self.returncode if self.returncode >= 0 else 128 + abs(self.returncode)

    @property
    def fault(self) -> str | None:
        """Return the native lane's existing typed-fault shape."""
        if self.output_overflow:
            return "output_overflow"
        if self.timed_out:
            return "timeout"
        return None


def _raw_record(stdout: bytes, stderr: bytes) -> dict[str, Any]:
    return {
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
    }


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        if process.poll() is None:
            process.kill()


def capture_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None,
    timeout_seconds: float,
    output_byte_limit: int,
    monotonic: Callable[[], float] | None = None,
) -> CapturedProcess:
    """Run ``argv`` with strict deadline and combined bounded pipe capture."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if output_byte_limit < 1:
        raise ValueError("output_byte_limit must be positive")
    clock = monotonic or time.monotonic
    process = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    streams = {"stdout": process.stdout, "stderr": process.stderr}
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    for name, stream in streams.items():
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)

    deadline = clock() + timeout_seconds
    timed_out = False
    output_overflow = False
    try:
        while True:
            now = clock()
            if now >= deadline:
                timed_out = True
                break
            returncode = process.poll()
            if not selector.get_map() and returncode is not None:
                break
            events = selector.select(min(0.05, deadline - now))
            for key, _mask in events:
                name = key.data
                retained = sum(len(buffer) for buffer in buffers.values())
                remaining = output_byte_limit + 1 - retained
                if remaining <= 0:
                    output_overflow = True
                    break
                try:
                    chunk = os.read(key.fd, min(65_536, remaining))
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[name].extend(chunk)
                if sum(len(buffer) for buffer in buffers.values()) > output_byte_limit:
                    output_overflow = True
                    break
            if output_overflow:
                break
        if timed_out or output_overflow:
            _terminate_process_group(process)
        returncode = process.wait()
    finally:
        selector.close()
        for stream in streams.values():
            stream.close()

    stdout_bytes = bytes(buffers["stdout"])
    stderr_bytes = bytes(buffers["stderr"])
    return CapturedProcess(
        returncode=returncode,
        timed_out=timed_out,
        output_overflow=output_overflow,
        raw=_raw_record(stdout_bytes, stderr_bytes),
        stdout=stdout_bytes,
        stderr=stderr_bytes,
    )
