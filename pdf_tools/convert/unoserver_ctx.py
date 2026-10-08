"""Backward-compatible context manager for removed listener management."""

from __future__ import annotations

import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = ["unoserver_listener"]


@contextmanager
def unoserver_listener(
    *,
    uno_port: int = 2002,
    xmlrpc_port: int = 2003,
    port: int | None = None,
    soffice_path: Path | None = None,
) -> Iterator[None]:
    """Accept the former listener context without starting a process.

    Parameters
    ----------
    uno_port : int, default 2002
        Retained for calling compatibility.
    xmlrpc_port : int, default 2003
        Retained for calling compatibility.
    port : int | None, default None
        Retained alias for ``uno_port``.
    soffice_path : Path | None, default None
        Retained for calling compatibility.

    Notes
    -----
    Deprecated for removal in the later public API overhaul. Word conversion
    now invokes LibreOffice directly and needs no listener.
    """
    warnings.warn(
        "unoserver_listener is deprecated; Word conversion no longer "
        "requires a listener.",
        DeprecationWarning,
        stacklevel=2,
    )
    yield
