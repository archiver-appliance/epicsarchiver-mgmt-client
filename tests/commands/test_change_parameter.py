import logging
from unittest.mock import MagicMock, call, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    OperationResult,
    SamplingMethod,
)
from epicsarchiver_mgmt.commands.change_parameter import change_parameter
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


def test_change_parameter_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful change_parameter operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1", "PV2"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    # Simulate the list comprehension result
    mock_change_parameter_results = [
        OperationResult(pv="PV1", statusCode=200, statusMessage="OK"),
        OperationResult(pv="PV2", statusCode=200, statusMessage="OK"),
    ]
    # Make the mock iterable and return specific results for each call
    mock_archiver.update_pv.side_effect = mock_change_parameter_results

    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
        {"pvName": "PV2", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status

    with (
        patch("epicsarchiver_mgmt.commands.change_parameter.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.change_parameter.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.change_parameter.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "epicsarchiver_mgmt.commands.change_parameter.validate_operation_results"
        ) as mock_validate_operation_results,
    ):
        change_parameter(archiver_fqdn, pvs, SamplingMethod.SCAN, None)

        mock_validate_pvs_status.assert_called_once_with(
            archiver_info=mock_archiver_info,
            pvs=pvs,
            expected_statuses=[ArchivingStatus.BeingArchived],
            existing_status_infos=existing_status,
        )
        # Check that change_parameter_pv was called for each PV
        mock_archiver.update_pv.assert_has_calls(
            [
                call("PV1", samplingmethod=SamplingMethod.SCAN, samplingperiod=1),
                call("PV2", samplingmethod=SamplingMethod.SCAN, samplingperiod=1),
            ],
            any_order=False,
        )
        # Check the validation call with the cast results
        mock_validate_operation_results.assert_called_once_with(
            pvs, mock_change_parameter_results, "changed parameters"
        )
        assert f"Changing sampling method and period of the PVs {pvs}" in caplog.text
        assert f"Using archiver {mock_archiver.info}" in caplog.text


def test_raise_http_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test change_parameter operation with HTTP error during API call."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pvs = ["PV1"]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "Internal Server Error"
    http_error = HTTPError(response=request_response)
    # Simulate error during the list comprehension by setting side_effect on the relevant method
    mock_archiver.update_pv = MagicMock(side_effect=http_error)

    existing_status = [
        {"pvName": "PV1", "status": "Paused", "appliance": "appliance1", "samplingPeriod": "1"},
    ]
    mock_archiver_info.get_pv_status.return_value = existing_status

    with (
        patch("epicsarchiver_mgmt.commands.change_parameter.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.change_parameter.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.change_parameter.validate_pvs_status") as mock_validate_pvs_status,
        patch(
            "epicsarchiver_mgmt.commands.change_parameter.validate_operation_results"
        ) as mock_validate_operation_results,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            change_parameter(archiver_fqdn, pvs, SamplingMethod.SCAN, 1)

        mock_validate_pvs_status.assert_called_once_with(
            archiver_info=mock_archiver_info,
            pvs=pvs,
            expected_statuses=[ArchivingStatus.BeingArchived],
            existing_status_infos=existing_status,
        )
        # The API method should have been called once before raising the error
        mock_archiver.update_pv.assert_called_once_with("PV1", samplingmethod=SamplingMethod.SCAN, samplingperiod=1)
        mock_validate_operation_results.assert_not_called()
        assert "Error changing sampling method and period of PVs" in caplog.text
        assert str(http_error) in caplog.text  # Check if the original error message is logged
        assert exc_info.value.__cause__ is http_error
