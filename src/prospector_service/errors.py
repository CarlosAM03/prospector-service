class EngineCancelled(Exception):
    """The Engine completed cooperative cancellation/cleanup; no HTTP cancel API."""


class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message
        super().__init__(code)


class EngineExecutionError(Exception):
    def __init__(self, code: str, *, runtime_unavailable: bool = False):
        self.code = code
        self.runtime_unavailable = runtime_unavailable
        super().__init__(code)
