from __future__ import annotations

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable, Coroutine, Generic, TypeVar


T = TypeVar("T")


async def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class AsyncClientAdapter:
    def __init__(self, client: Any) -> None:
        self._client = client

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._client, name)
        if not callable(value):
            return value

        @wraps(value)
        def call(*args: Any, **kwargs: Any) -> Any:
            result = value(*args, **kwargs)
            if inspect.isawaitable(result):
                return result
            return AwaitableValue(result)

        return call


def async_client(client: Any) -> AsyncClientAdapter:
    return AsyncClientAdapter(client)


class AwaitableResult(Generic[T]):
    def __init__(self, coroutine: Coroutine[Any, Any, T]) -> None:
        self._coroutine: Coroutine[Any, Any, T] | None = coroutine
        self._resolved = False
        self._value: T | None = None
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self._value = asyncio.run(self._resolve_async())

    async def _resolve_async(self) -> T:
        if not self._resolved:
            if self._coroutine is None:
                raise RuntimeError("AwaitableResult has no coroutine to resolve.")
            self._value = await self._coroutine
            self._coroutine = None
            self._resolved = True
        return self._value  # type: ignore[return-value]

    def _resolve_sync(self) -> T:
        if not self._resolved:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                self._value = asyncio.run(self._resolve_async())
            else:
                raise RuntimeError("Service result must be awaited inside an active event loop.")
        return self._value  # type: ignore[return-value]

    def __await__(self):
        return self._resolve_async().__await__()

    def __iter__(self):
        return iter(self._resolve_sync())

    def __len__(self) -> int:
        return len(self._resolve_sync())  # type: ignore[arg-type]

    def __bool__(self) -> bool:
        return bool(self._resolve_sync())

    def __getitem__(self, key: Any) -> Any:
        return self._resolve_sync()[key]  # type: ignore[index]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._resolve_sync(), name)

    def __eq__(self, other: object) -> bool:
        return self._resolve_sync() == other

    __hash__ = object.__hash__

    def __repr__(self) -> str:
        if self._resolved:
            return repr(self._value)
        return "<AwaitableResult unresolved>"

    def __str__(self) -> str:
        return str(self._resolve_sync())


class AwaitableValue(Generic[T]):
    def __init__(self, value: T) -> None:
        self._value = value

    async def _resolve_async(self) -> T:
        return self._value

    def __await__(self):
        return self._resolve_async().__await__()

    def __iter__(self):
        return iter(self._value)

    def __len__(self) -> int:
        return len(self._value)  # type: ignore[arg-type]

    def __bool__(self) -> bool:
        return bool(self._value)

    def __getitem__(self, key: Any) -> Any:
        return self._value[key]  # type: ignore[index]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._value, name)

    def __eq__(self, other: object) -> bool:
        return self._value == other

    def __repr__(self) -> str:
        return repr(self._value)

    def __str__(self) -> str:
        return str(self._value)


def dual_mode(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., AwaitableResult[T]]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> AwaitableResult[T]:
        return AwaitableResult(func(*args, **kwargs))

    return wrapper


def dual_mode_class(cls: type) -> type:
    for name, member in list(cls.__dict__.items()):
        if name.startswith("_"):
            continue
        if isinstance(member, staticmethod) and inspect.iscoroutinefunction(member.__func__):
            setattr(cls, name, staticmethod(dual_mode(member.__func__)))
        elif isinstance(member, classmethod) and inspect.iscoroutinefunction(member.__func__):
            setattr(cls, name, classmethod(dual_mode(member.__func__)))
        elif inspect.iscoroutinefunction(member):
            setattr(cls, name, dual_mode(member))
    return cls


__all__ = ["async_client", "AwaitableResult", "AwaitableValue", "dual_mode", "dual_mode_class", "maybe_await"]
