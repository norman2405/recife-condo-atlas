from __future__ import annotations

import logging
import sys


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("recife_condo_atlas")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    return logger
