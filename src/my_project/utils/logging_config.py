import logging
from pathlib import Path


def configure_logging(log_dir: Path) -> None:
    """Configure application-wide logging."""

    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "debug.log"

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(
                log_file,
                mode="a",
                encoding="utf-8",
            ),
            # logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    # Reduce noise from libraries we don't control.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("qasync").setLevel(logging.WARNING)
