"""Context manager that starts a transient *unoserver* listener.

The listener speaks UNO over a TCP socket (default 127.0.0.1:2002). Calls to
``unoconvert`` in the same process tree can then use ``--port 2002`` to reuse
that single LibreOffice instance, avoiding the heavy start-up cost per file.
"""

from __future__ import annotations

import contextlib
import shutil
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

__all__ = ["unoserver_listener"]

_UNOSERVER_CMD = shutil.which(
    "unoserver"
)  # provided by the *unoserver* PyPI pkg
_DEFAULT_PORT = 2002
_STARTUP_TIMEOUT_S = 15


def _wait_until_port_listens(port: int, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:  # 0 => success
                return
        time.sleep(0.25)
    raise TimeoutError(
        f"unoserver did not open port {port} within {timeout}s."
    )


@contextlib.contextmanager
def unoserver_listener(
    *, port: int = _DEFAULT_PORT, soffice_path: Path | None = None
) -> Iterator[None]:
    """Launch *unoserver* in the background for batch conversions.

    Parameters
    ----------
    port
        TCP port the listener should bind to (default 2002).
    soffice_path
        Custom path to the LibreOffice ``soffice`` binary if it is not on
        ``$PATH``.

    Raises
    ------
    FileNotFoundError
        If *unoserver* (or *soffice* when explicitly provided) is not found.
    TimeoutError
        If the listener does not start within the allotted timeout.
    """
    if _UNOSERVER_CMD is None:
        raise FileNotFoundError(
            "The 'unoserver' executable was not found on $PATH. "
            "Install it with:  pip install unoserver"
        )

    cmd = [_UNOSERVER_CMD]
    if soffice_path is not None:
        if not soffice_path.exists():
            raise FileNotFoundError(
                f"soffice binary not found at {soffice_path}"
            )
        cmd.extend(["--soffice", str(soffice_path)])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        _wait_until_port_listens(port, _STARTUP_TIMEOUT_S)
        yield  # ---- caller executes batch work here ----
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
