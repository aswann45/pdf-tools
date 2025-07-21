"""
Async Typer implementation.

Drop‑in replacement for :class:`typer.Typer` that allows **async/await**
commands *without* manual event‑loop plumbing.

Typer (and Click underneath) expects synchronous callables.  To support native
``async def`` commands we subclass :class:`typer.Typer` and wrap coroutine
functions with :func:`asyncio.run` *only when needed*.  The public API remains
unchanged—import :class:`AsyncTyper` instead of :class:`typer.Typer` and the
rest of your CLI code can freely mix sync and async commands.

Example
-------
>>> from pdf_tools.cli.async_typer import AsyncTyper
>>> import typer, asyncio
>>>
>>> cli = AsyncTyper()
>>>
>>> @cli.command()
... async def greet(name: str):
...     await asyncio.sleep(0.1)
...     typer.echo(f"Hello {name}!")
>>>
>>> # `pdf-tools greet Bob` now runs happily without explicit loop management.
"""

import asyncio
import inspect
from collections.abc import Callable
from functools import partial, wraps
from typing import Any, Final

from typer import Typer

__all__: Final = [
    "AsyncTyper",
]


class AsyncTyper(Typer):
    """A :class:`typer.Typer` subclass that supports *async* commands.

    The class overrides :meth:`typer.Typer.command` and
    :meth:`typer.Typer.callback` to detect coroutine functions and wrap them in
    a small sync shim that executes :func:`asyncio.run`.  Non‑coroutine
    functions are registered untouched, so performance and signature
    introspection remain identical to upstream Typer.
    """

    @staticmethod
    def maybe_run_async(decorator: Callable, f: Callable) -> Any:
        """Invoke *decorator* with either *f* or an async shim.

        Parameters
        ----------
        decorator : Callable[[Callable], Any]
            The Typer (Click) decorator returned by ``Typer.command`` or
            ``Typer.callback``.
        f : Callable
            The original user‑defined function (may be a coroutine).

        Returns
        -------
        Callable
            The *original* function *f*.  Returning *f* from a decorator chain
            preserves the reference Typer stores internally.
        """
        if inspect.iscoroutinefunction(f):

            @wraps(f)
            def runner(*args: Any, **kwargs: Any) -> Any:
                """Sync shim to drive the coroutine via :func:`asyncio.run`."""
                return asyncio.run(f(*args, **kwargs))

            decorator(runner)
        else:
            decorator(f)
        return f

    def callback(self, *args: Any, **kwargs: Any) -> Any:
        """Return a Typer *callback* decorator that supports coroutines."""
        decorator = super().callback(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """Return a Typer *command* decorator that supports coroutines."""
        decorator = super().command(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)
