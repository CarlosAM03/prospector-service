import logging

import uvicorn
from pydantic import ValidationError

from .config import Settings
from .main import create_app


def main() -> None:
    try:
        settings = Settings.from_env()
    except ValidationError:
        raise SystemExit("Invalid Service configuration; check environment") from None
    logging.basicConfig(level=settings.log_level)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        workers=1,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
