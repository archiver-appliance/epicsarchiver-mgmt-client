"""Tests for archiver mgmt operations module."""

from __future__ import annotations

import json
import logging

import pytest
import responses
from epicsarchiver.common import ArchDbrType
from requests import HTTPError

from archmgmt.mgmt.archiver import (
    ArchivePVRequest,
    ArchiverMgmt,
    PutInfoType,
    SamplingMethod,
    Storage,
)

LOG: logging.Logger = logging.getLogger(__name__)

TEST_DOMAIN = "archiver.example.org"


@responses.activate
def test_archive_pv() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = [
        {"pvName": "ISrc-010:HVAC-HT:AmbHumR", "status": "Archive request submitted"},
    ]
    responses.add(
        responses.POST,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/archivePV",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.archive_pv("ISrc-010:HVAC-HT:AmbHumR")
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_archive_pv_with_extra_args() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = [
        {"pvName": "ISrc-010:HVAC-HT:AmbHumR", "status": "Archive request submitted"},
    ]
    responses.add(
        responses.POST,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/archivePV",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.archive_pv(
        "ISrc-010:HVAC-HT:AmbHumR",
        sampling_period=2.0,
        sampling_method=SamplingMethod.SCAN,
    )
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_archive_pvs() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = [{"pvName": "MY:PV", "status": "Already submitted"}]
    responses.add(
        responses.POST,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/archivePV",
        json=data,
        status=200,
    )
    pv_requests = [ArchivePVRequest("first:pv"), ArchivePVRequest("second:pv")]
    r = archiver.archive_pv_requests(pv_requests)
    assert len(responses.calls) == 1
    body_text = responses.calls[0].request.body
    assert body_text is not None
    body = json.loads(body_text)
    assert body == [{"pv": "first:pv"}, {"pv": "second:pv"}]
    assert r == data


@responses.activate
def test_pause_pv_single() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = [
        {
            "pvName": "MY:PV",
            "engine_desc": "Successfully paused the archiving of PV MY:PV",
            "engine_pvName": "MY:PV",
            "engine_status": "ok",
            "etl_status": "ok",
            "etl_desc": "Successfully removed PV MY:PV from the cluster",
            "etl_pvName": "MY:PV",
            "status": "ok",
        },
    ]

    pv = "KLYS*"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/pauseArchivingPV?pv={pv}",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.pause_pv(pv)
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_pause_pv_comma_separated_list() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = [{"validation": "Unable to pause PV MY:PV"}]
    pvs = "mypv1,mypv2"
    responses.add(
        responses.POST,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/pauseArchivingPV",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.pause_pv(pvs)
    assert len(responses.calls) == 1  # ignore for https://github.com/getsentry/responses/pull/690

    assert responses.calls[0].request.body == pvs
    assert r == data


@responses.activate
def test_resume_pv_single() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = [{"validation": "Unable to resume PV MY:PV"}]
    pv = "KLYS*"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/resumeArchivingPV?pv={pv}",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.resume_pv(pv)
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_resume_pv_comma_separated_list() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = [
        {"validation": "Unable to pause PV mypv1"},
        {"validation": "Unable to pause PV mypv2"},
    ]
    pvs = "mypv1,mypv2"
    responses.add(
        responses.POST,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/resumeArchivingPV",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.resume_pv(pvs)
    assert len(responses.calls) == 1  # ignore for https://github.com/getsentry/responses/pull/690

    assert responses.calls[0].request.body == pvs
    assert r == data


@responses.activate
def test_abort_pv() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = ["1", "2", "3"]
    pv = "LEBT-010:PBI-NPM-001:HCAM-COM"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/abortArchivingPV?pv=LEBT-010%3APBI-NPM-001%3AHCAM-COM",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.abort_pv(pv)
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_delete_pv_data_false() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = ["1", "2", "3"]
    pv = "LEBT-010:PBI-NPM-001:HCAM-COM"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/deletePV?pv=LEBT-010%3APBI-NPM-001%3AHCAM-COM&delete_data=False",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.delete_pv(pv)
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_delete_pv_data_true() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = ["1", "2", "3"]
    pv = "LEBT-010:PBI-NPM-001:HCAM-COM"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/deletePV?pv=LEBT-010%3APBI-NPM-001%3AHCAM-COM&delete_data=True",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.delete_pv(pv, delete_data=True)
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_update_pv() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = ["1", "2", "3"]
    pv = "mypv"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/changeArchivalParameters?pv={pv}&samplingperiod=2.0",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.update_pv(pv, 2.0)
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_update_pv_samplingmethod() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    data = ["1", "2", "3"]
    pv = "mypv"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/changeArchivalParameters?pv={pv}&samplingperiod=2.0&samplingmethod=SCAN",
        json=data,
        status=200,
        match_querystring=True,
    )
    r = archiver.update_pv(pv, 2.0, "SCAN")
    assert len(responses.calls) == 1
    assert r == data


@responses.activate
def test_add_alias_ok() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    pv = "MY:PV"
    newname = "NEW:PV"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/addAlias?pv={pv}&aliasname={newname}",
        json={"status": "ok", "desc": f"Added an alias {newname} for PV {pv}"},
        status=200,
        match_querystring=True,
    )
    response = archiver.add_alias(pv, newname)
    assert len(responses.calls) == 1
    assert response == {"status": "ok", "desc": f"Added an alias {newname} for PV {pv}"}


@responses.activate
def test_add_alias_pv_does_not_exist() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    pv = "MY:PV"
    newname = "NEW:PV"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/addAlias?pv={pv}&aliasname={newname}",
        status=500,
        match_querystring=True,
    )
    with pytest.raises(HTTPError):
        archiver.add_alias(pv, newname)


@responses.activate
def test_rename_and_append_success(caplog: pytest.LogCaptureFixture) -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    old = "MY:PV"
    new = "NEW:PV"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/appendAndAliasPV?olderpv={old}&newerpv={new}&storage=MTS",
        json={
            "addAlias": "ok",
            "deleteOlder": "ok",
            "deleteNewer": "ok",
            "status": "ok",
        },
        status=200,
        match_querystring=True,
    )
    with caplog.at_level(logging.DEBUG):
        archiver.rename_and_append(old, new, Storage.MTS)
    captured_log = caplog.text
    assert len(responses.calls) == 1
    assert "ok" in captured_log


@responses.activate
def test_rename_and_append_fail_pv_error_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    old = "MY:PV"
    new = "NEW:PV"
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/appendAndAliasPV?olderpv={old}&newerpv={new}&storage=MTS",
        json={"validation": "error during appendAndAliasPV"},
        status=200,
        match_querystring=True,
    )
    with caplog.at_level(logging.DEBUG):
        archiver.rename_and_append(old, new, Storage.MTS)
    captured_log = caplog.text
    LOG.info(captured_log)
    assert len(responses.calls) == 1
    assert "error during appendAndAliasPV" in captured_log


@responses.activate
def test_change_type() -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    pv = "MY:PV"
    new_type = ArchDbrType.DBR_SCALAR_DOUBLE
    responses.add(
        responses.GET,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/changeTypeForPV?pv={pv}&newtype=DBR_SCALAR_DOUBLE",
        json={"status": "ok"},
        status=200,
        match_querystring=True,
    )
    r = archiver.change_type(pv, new_type)
    assert len(responses.calls) == 1
    assert r == {"status": "ok"}


@responses.activate
def test_put_pv_type_info_ok(caplog: pytest.LogCaptureFixture) -> None:
    archiver = ArchiverMgmt(TEST_DOMAIN)
    pv = "MY:PV"
    newtypeinfo = {
        "hostName": "idmz-ro-epics-gw-tn.esss.lu.se",
        "paused": "false",
        "creationTime": "2025-01-23T12:04:58.973Z",
        "lowerAlarmLimit": "NaN",
        "precision": "0.0",
        "lowerCtrlLimit": "10.0",
        "units": "degC",
        "computedBytesPerEvent": "18",
        "computedEventRate": "18.366667",
        "usePVAccess": "false",
        "computedStorageRate": "345.35",
        "modificationTime": "2025-01-23T12:04:58.973Z",
        "upperDisplayLimit": "150.0",
        "upperWarningLimit": "30.0",
        "DBRType": "DBR_SCALAR_DOUBLE",
        "dataStores": [
            "pb://localhost?name=STS&rootFolder=${ARCHAPPL_SHORT_TERM_FOLDER}&partitionGranularity=PARTITION_HOUR&consolidateOnShutdown=true",
            "pb://localhost?name=MTS&rootFolder=${ARCHAPPL_MEDIUM_TERM_FOLDER}&partitionGranularity=PARTITION_DAY&hold=2&gather=1",
            "pb://localhost?name=LTS&rootFolder=${ARCHAPPL_LONG_TERM_FOLDER}&partitionGranularity=PARTITION_YEAR",
        ],
        "upperAlarmLimit": "50.0",
        "userSpecifiedEventRate": "0.0",
        "policyName": "2HzPVs",
        "useDBEProperties": "false",
        "hasReducedDataSet": "false",
        "lowerWarningLimit": "NaN",
        "applianceIdentity": "localhost",
        "scalar": "true",
        "pvName": "DTL-020:EMR-TT-002:Temp",
        "upperCtrlLimit": "150.0",
        "lowerDisplayLimit": "10.0",
        "samplingPeriod": "1.0",
        "elementCount": "1",
        "samplingMethod": "MONITOR",
        "archiveFields": ["HIHI", "HIGH", "LOW", "LOLO", "LOPR", "HOPR"],
        "extraFields": {
            "ADEL": "0.0",
            "MDEL": "0.0",
            "SCAN": "Passive",
            "NAME": "DTL-020:EMR-TT-002:Temp",
            "RTYP": "ai",
        },
    }
    responses.add(
        responses.POST,
        f"http://{TEST_DOMAIN}:17665/mgmt/bpl/putPVTypeInfo?pv={pv}&createnew=true&override=false",
        json=newtypeinfo,
        status=200,
        match_querystring=True,
    )

    with caplog.at_level(logging.DEBUG):
        archiver.put_pv_type_info(pv, newtypeinfo, PutInfoType.CreateNew)
    captured_log = caplog.text

    assert len(responses.calls) == 1
    assert "Put type info" in captured_log
