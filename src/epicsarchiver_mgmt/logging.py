"""Sets up logging for the application."""

import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from dateutil import tz
from rich.logging import RichHandler

HOME_LOG = Path.home() / ".local" / "archiver_mgmt" / "logs"

if not HOME_LOG.exists():
    HOME_LOG.mkdir(parents=True)

HOME_LOG_LOCATION = HOME_LOG / "archiver_mgmt.log"

LOG: logging.Logger = logging.getLogger(__name__)


def log_location(command_path: str) -> Path:
    """Get the location of the log file.

    Args:
        command_path (str): The full path of the command.

    Returns:
        Path: The location of the log file.
    """
    current_time = datetime.datetime.now(tz=tz.tzlocal()).strftime("%Y-%m-%dT%H_%M_%S")
    return Path(f"{current_time}_{command_path.replace(" ", "_")}_archiver_mgmt.log")


def setup_file_handler(command_path: str) -> logging.Handler:
    """Set up file logging for the command.

    Args:
        command_path (str): The full path of the command.

    Returns:
        logging.Handler: The file handler for the command.
    """
    current_command_log = log_location(command_path)

    LOG.info("Creating LOG file at %s", current_command_log)

    file_handler = logging.FileHandler(current_command_log)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    root.addHandler(file_handler)
    return file_handler


formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

timed_rotating_file_handler = TimedRotatingFileHandler(HOME_LOG_LOCATION)
timed_rotating_file_handler.setFormatter(formatter)
timed_rotating_file_handler.setLevel(logging.DEBUG)


logging.basicConfig(level=logging.DEBUG, handlers=[])
root = logging.getLogger()
root.addHandler(timed_rotating_file_handler)


rich_handler = RichHandler()
rich_handler.setFormatter(formatter)
rich_handler.setLevel(logging.INFO)
root.addHandler(rich_handler)
