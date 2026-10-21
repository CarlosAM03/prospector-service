from typing import Protocol

from .schemas import BusinessResult, ProspectingQuery


class CancellationControl(Protocol):
    def request_cancel(self) -> None: ...
    def raise_if_cancelled(self) -> None: ...


class EnginePort(Protocol):
    def probe(self) -> bool: ...
    def new_token(self) -> CancellationControl: ...
    def execute(
        self, query: ProspectingQuery, token: CancellationControl
    ) -> tuple[BusinessResult, ...]: ...


class UnavailableEngine:
    """Fail closed when the mandatory Engine package cannot be imported."""

    def probe(self) -> bool:
        return False

    def new_token(self):
        raise RuntimeError("Engine unavailable")

    def execute(self, query, token):
        raise RuntimeError("Engine unavailable")
