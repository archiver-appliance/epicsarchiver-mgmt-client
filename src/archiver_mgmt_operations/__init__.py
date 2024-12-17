# SPDX-FileCopyrightText: 2024-present skybrewer <sky.brewer@ess.eu>
#
# SPDX-License-Identifier: MIT

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
CURRENT_COMMAND_LOG = Path(datetime.datetime.now(tz=tz.tzlocal()).strftime("%Y-%m-%dT%H_%M_%S") + "_archiver_mgmt.log")

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

timed_rotating_file_handler = TimedRotatingFileHandler(HOME_LOG_LOCATION)
timed_rotating_file_handler.setFormatter(formatter)
timed_rotating_file_handler.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(CURRENT_COMMAND_LOG)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.DEBUG)

rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(formatter)
rich_handler.setLevel(logging.INFO)

logging.basicConfig(level=logging.DEBUG, handlers=[])

root = logging.getLogger()
root.addHandler(timed_rotating_file_handler)
root.addHandler(file_handler)
root.addHandler(rich_handler)
