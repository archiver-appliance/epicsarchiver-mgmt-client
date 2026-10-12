"""Tests for the archiver report endpoints."""

import datetime

import pytest
import pytz
import responses

from epicsarchiver_mgmt.archiver.reports import DEFAULT_QUERY_LIMIT, ArchiverReports
from epicsarchiver_mgmt.models.stat_responses import (
    ConnectionStatus,
    DisconnectedPV,
    DroppedPVResponse,
    DroppedReason,
    HighStorageRate,
    LostConnections,
    PausedPVResponse,
    SilentPV,
    parse_archiver_datetime,
)

HOST = "archiver.example.org"
BASE_URL = f"http://{HOST}:17665/mgmt/bpl"


@responses.activate
def test_get_pvs_dropped() -> None:
    reason = DroppedReason.BufferOverflow
    url = f"{BASE_URL}/getPVsByDroppedEventsBuffer?limit={DEFAULT_QUERY_LIMIT}"
    responses.get(url, json=[{"eventsDropped": "30", "pvName": "MY:PV"}])

    archiver = ArchiverReports(HOST)
    pvs_dropped = archiver.get_pvs_dropped(reason)

    assert len(responses.calls) == 1
    assert [DroppedPVResponse("MY:PV", 30, reason)] == pvs_dropped


@responses.activate
def test_get_disconnected_pvs() -> None:
    url = f"{BASE_URL}/getCurrentlyDisconnectedPVs"
    responses.get(
        url,
        json=[
            {
                "hostName": "N/A",
                "connectionLostAt": "Sep/14/2023 16:00:18 +02:00",
                "pvName": "MY:PV",
                "instance": HOST,
                "commandThreadID": "6",
                "noConnectionAsOfEpochSecs": "1694700018",
                "lastKnownEvent": "Aug/25/2023 15:38:17 +02:00",
            },
        ],
    )

    archiver = ArchiverReports(HOST)
    pvs_disconnected = archiver.get_disconnected_pvs()

    assert len(responses.calls) == 1
    assert [
        DisconnectedPV(
            "MY:PV",
            "N/A",
            datetime.datetime.fromisoformat("2023-09-14T16:00:18+02:00").replace(
                tzinfo=pytz.utc,
            ),
            HOST,
            6,
            1694700018,
            datetime.datetime.fromisoformat("2023-08-25T15:38:17+02:00").replace(
                tzinfo=pytz.utc,
            ),
        ),
    ] == pvs_disconnected


@responses.activate
def test_get_silent_pvs() -> None:
    url = f"{BASE_URL}/getSilentPVsReport?limit={DEFAULT_QUERY_LIMIT}"
    responses.get(
        url,
        json=[
            {
                "pvName": "MY:PV",
                "instance": HOST,
                "lastKnownEvent": "Aug/25/2023 15:38:17 +02:00",
            },
        ],
    )

    archiver = ArchiverReports(HOST)
    pvs_response = archiver.get_silent_pvs()

    assert len(responses.calls) == 1
    assert [
        SilentPV(
            "MY:PV",
            HOST,
            datetime.datetime.fromisoformat("2023-08-25T15:38:17+02:00").replace(
                tzinfo=pytz.utc,
            ),
        ),
    ] == pvs_response


@responses.activate
def test_get_lost_connections_pvs() -> None:
    url = f"{BASE_URL}/getLostConnectionsReport?limit={DEFAULT_QUERY_LIMIT}"
    responses.get(
        url,
        json=[
            {
                "currentlyConnected": "Yes",
                "pvName": "MY:PV",
                "instance": HOST,
                "lostConnections": "2586",
            },
        ],
    )

    archiver = ArchiverReports(HOST)
    pvs_response = archiver.get_lost_connections_pvs()

    assert len(responses.calls) == 1
    assert [
        LostConnections(
            "MY:PV",
            ConnectionStatus.CurrentlyConnected,
            HOST,
            2586,
        ),
    ] == pvs_response


@responses.activate
def test_get_paused_pvs() -> None:
    url = f"{BASE_URL}/getPausedPVsReport"
    responses.get(
        url,
        json=[
            {
                "pvName": "MY:PV",
                "instance": "archiver",
                "modificationTime": "Sep/12/2023 16:38:56 +02:00",
            },
        ],
    )

    archiver = ArchiverReports(HOST)
    pvs_response = archiver.get_paused_pvs()

    assert len(responses.calls) == 1
    assert [PausedPVResponse("MY:PV", "archiver", "Sep/12/2023 16:38:56 +02:00")] == pvs_response


@responses.activate
def test_get_storage_rates() -> None:
    url = f"{BASE_URL}/getStorageRateReport?limit={DEFAULT_QUERY_LIMIT}"
    responses.get(
        url,
        json=[
            {
                "pvName": "MY:PV",
                "storageRate_MBperDay": "1099.2894956029622",
                "storageRate_KBperHour": "46903.01847905972",
                "storageRate_GBperYear": "391.8365877881653",
            },
        ],
    )

    archiver = ArchiverReports(HOST)
    pvs_response = archiver.get_storage_rates()

    assert len(responses.calls) == 1
    assert [
        HighStorageRate(
            "MY:PV",
            1099.2894956029622,
            46903.01847905972,
            391.8365877881653,
        ),
    ] == pvs_response


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (
            "Feb/07/2024 20:55:42 UTC",
            datetime.datetime(
                year=2024,
                month=2,
                day=7,
                hour=20,
                minute=55,
                second=42,
                tzinfo=pytz.utc,
            ),
        ),
        (
            "Feb/07/2024 20:55:42 Z",
            datetime.datetime(
                year=2024,
                month=2,
                day=7,
                hour=20,
                minute=55,
                second=42,
                tzinfo=pytz.utc,
            ),
        ),
        ("Never", None),
        ("", None),
    ],
)
def test_parse_archiver_datetime(
    test_input: str,
    expected: datetime.datetime | None,
) -> None:
    assert parse_archiver_datetime(test_input) == expected
