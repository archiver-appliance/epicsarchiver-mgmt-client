import logging
from unittest.mock import MagicMock, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus

from epicsarchiver_mgmt.commands.statuses import get_statuses


def test_statuses_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful fetch statuses."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
        {"pvName": "PV2", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status

    with (
        patch("epicsarchiver_mgmt.commands.statuses.ArchiverMgmtInfo", return_value=mock_archiver_info),
    ):
        get_statuses(archiver_fqdn, pvs, filter_statuses=[ArchivingStatus.Paused])
