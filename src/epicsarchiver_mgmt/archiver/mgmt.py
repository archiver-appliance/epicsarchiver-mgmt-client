"""Archiver Mgmt operations module."""

from __future__ import annotations

import enum
import logging
from collections.abc import Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from epicsarchiver.mgmt.archiver_mgmt_info import (
    ArchiverMgmtInfo,
)

if TYPE_CHECKING:
    from epicsarchiver.common import ArchDbrType

LOG: logging.Logger = logging.getLogger(__name__)


class Storage(enum.StrEnum):
    """Represents the different storage levels of the archiver appliance."""

    STS = "STS"
    MTS = "MTS"
    LTS = "LTS"


class PutInfoType(enum.Enum):
    """Represents the different types of put type info."""

    Override = enum.auto()
    CreateNew = enum.auto()


TypeInfo = dict[str, Collection[str]]
OperationResult = dict[str, str]
OperationResultList = list[OperationResult]


class EpicsProto(enum.StrEnum):
    """Represents the different input protocols of the archiver appliance."""

    CA = "CA"
    PVA = "PVA"


class SamplingMethod(enum.StrEnum):
    """Represents the different sampling methods of the archiver appliance."""

    SCAN = "SCAN"
    MONITOR = "MONITOR"


@dataclass
class ArchivePVRequest:
    """Information to archive a PV."""

    pv: str
    samplingmethod: SamplingMethod | None = None
    samplingperiod: str | None = None
    controllingPV: str | None = None  # noqa: N815
    policy: str | None = None
    appliance: str | None = None

    def as_dict(self) -> dict[str, str]:
        """Return the object as a dictionary."""
        output = {"pv": self.pv}
        if self.samplingmethod:
            output["samplingmethod"] = self.samplingmethod.value
        if self.samplingperiod:
            output["samplingperiod"] = self.samplingperiod
        if self.controllingPV:
            output["controllingPV"] = self.controllingPV
        if self.policy:
            output["policy"] = self.policy
        if self.appliance:
            output["appliance"] = self.appliance
        return output


class ArchiverMgmt(ArchiverMgmtInfo):
    """Mgmt Operations EPICS Archiver Appliance client.

    Hold a session to the Archiver Appliance web application and use the mgmt interface.

    Args:
        hostname: EPICS Archiver Appliance hostname [default: localhost]
        port: EPICS Archiver Appliance management port [default: 17665]
    """

    # EPICS Archiver Appliance documentation of mgmt endpoints:
    # https://epicsarchiver.readthedocs.io/en/latest/developer/mgmt_scriptables.html

    def archive_pv(
        self,
        pv: str,
        *,
        sampling_period: float | None = None,
        sampling_method: SamplingMethod | None = None,
        controlling_pv: str | None = None,
        policy: str | None = None,
        appliance: str | None = None,
        protocol: EpicsProto = EpicsProto.CA,
    ) -> OperationResultList:
        """Archive a PV.

        Args:
            pv (str): PV name.
            sampling_period (str | None, optional): The sampling period, i.e. 1.0 is 1Hz.
                Defaults to None.
            sampling_method (SamplingMethod | None, optional): The sampling method, SCAN or MONITOR.
                Defaults to None.
            controlling_pv (str | None, optional): A pv to control when to archive this pv.
                Defaults to None.
            policy (str | None, optional): The policy, can be found at /mgmt/bpl/getPolicyList.
                Defaults to None.
            appliance (str | None, optional): Can specify a specific appliance.
                Defaults to None.
            protocol (EpicsProto, optional): Protocol to use. Defaults to EpicsProto.CA.

        Returns:
            OperationResultList: _description_
        """
        return self.archive_pv_requests([
            ArchivePVRequest(
                pv=f"pva://{pv}" if protocol is EpicsProto.PVA else pv,
                samplingmethod=sampling_method,
                samplingperiod=str(sampling_period),
                controllingPV=controlling_pv,
                policy=policy,
                appliance=appliance,
            )
        ])

    def archive_pv_requests(self, pv_requests: list[ArchivePVRequest]) -> OperationResultList:
        """Archive a list of PVs with the given parameters.

        Args:
            pv_requests (list[ArchivePVRequest]): The pv requests.

        Returns:
            OperationResultList: Result of the operation.
        """
        request_data = [request.as_dict() for request in pv_requests]
        LOG.debug("Archiving PVs %s", request_data)
        r = self._post("/archivePV", json=request_data)
        return cast("OperationResultList", r.json())

    def pause_pv(self, pv: str) -> OperationResultList | OperationResult:
        """Pause the archiving of a PV(s).

        Args:
            pv: name of the pv. Can be a GLOB wildcards or a list of
                comma separated names.

        Returns:
            list of submitted PVs
        """
        response = self._get_or_post("/pauseArchivingPV", pv)
        if "," not in pv:
            return cast("OperationResult", response)
        return cast("OperationResultList", response)

    def resume_pv(self, pv: str) -> OperationResultList | OperationResult:
        """Resume the archiving of a PV(s).

        Args:
            pv: name of the pv. Can be a GLOB wildcards or a list of
                comma separated names.

        Returns:
            list of submitted PVs
        """
        response = self._get_or_post("/resumeArchivingPV", pv)
        if "," not in pv:
            return cast("OperationResult", response)
        return cast("OperationResultList", response)

    def abort_pv(self, pv: str) -> list[str]:
        """Abort any pending requests for archiving this PV.

        Args:
            pv: name of the pv.

        Returns:
            list of submitted PVs
        """
        r = self._get("/abortArchivingPV", params={"pv": pv})
        return cast("list[str]", r.json())

    def add_alias(self, pv: str, alias_name: str) -> OperationResult:
        """Add an alias to a pv.

        Args:
            pv: PV to add alias.
            alias_name: name of alias to add to pv.

        Returns:
            OperationResult: Status of action and description.
        """
        r = self._get("/addAlias", params={"pv": pv, "aliasname": alias_name})
        r_json = r.json()
        return cast("OperationResult", r_json)

    def remove_alias(self, pv: str, alias_name: str) -> OperationResult:
        """Remove an alias to a pv.

        Args:
            pv: PV to remove alias.
            alias_name: name of alias to remove from pv.

        Returns:
            OperationResult: Status of action and description.
        """
        r = self._get("/removeAlias", params={"pv": pv, "aliasname": alias_name})
        r_json = r.json()
        return cast("OperationResult", r_json)

    def delete_pv(
        self,
        pv: str,
        delete_data: bool = False,  # noqa: FBT002, FBT001
    ) -> list[str]:
        """Stop archiving the specified PV.

        The PV needs to be paused first.

        Args:
            pv: name of the pv.
            delete_data: delete the data that has already been recorded.
                Default to False.

        Returns:
            list of submitted PVs
        """
        r = self._get("/deletePV", params={"pv": pv, "delete_data": delete_data})
        return cast("list[str]", r.json())

    def rename_pv(self, pv: str, newname: str) -> OperationResult:
        """Rename this pv to a new name.

        The PV needs to be paused first.

        Args:
            pv (str): name of the pv.
            newname (str): new name of the pv

        Returns:
            OperationResult: Status of action and description. Example:
                {"status":"ok","desc":"Successfully renamed PV PV1 to PV2"}
        """
        r = self._get("/renamePV", params={"pv": pv, "newname": newname})
        return cast("OperationResult", r.json())

    def update_pv(
        self,
        pv: str,
        samplingperiod: float,
        samplingmethod: str | None = None,
    ) -> list[str]:
        """Change the archival parameters for a PV.

        Args:
            pv: name of the pv.
            samplingperiod: the new sampling period in seconds.
            samplingmethod: the new sampling method [SCAN|MONITOR]

        Returns:
            list of submitted PV
        """
        params = {"pv": pv, "samplingperiod": samplingperiod}
        if samplingmethod:
            params["samplingmethod"] = samplingmethod
        r = self._get("/changeArchivalParameters", params=params)
        return cast("list[str]", r.json())

    def rename_and_append(self, old: str, new: str, storage: Storage) -> OperationResult:
        """Appends the data for an older PV into a newer PV.

        The older PV is deleted and an alias mapping the older PV name to
        the new PV is added.

        Args:
            old (str): The name of the older pv.
                The data for this PV will be appended to the newer PV and then deleted.
            new (str): The name of the newer pv.
            storage (Storage):  The name of the store to consolidate data
                before appending.

        Returns:
            OperationResultList: Result of the operation
        """
        response = self._get(
            "/appendAndAliasPV",
            params={"olderpv": old, "newerpv": new, "storage": storage},
        )
        LOG.debug("/appendAndAliasPV response %s", response.json())
        return cast("OperationResult", response.json())

    def change_type(self, pv: str, new_type: ArchDbrType) -> OperationResult:
        """Change the type of a pv to a new type.

        Args:
            pv (str): Name of the PV
            new_type (ArchDbrType): New DBR_TYPE

        Returns:
            OperationResult
        """
        LOG.info("Change type of pv %s to %s", pv, new_type)
        response = self._get("/changeTypeForPV", params={"pv": pv, "newtype": new_type.name})
        return cast("OperationResult", response.json())

    def put_pv_type_info(self, pv: str, type_info: TypeInfo, put_info_type: PutInfoType) -> TypeInfo:
        """Put the type info for a PV.

        Args:
            pv (str): Name of the PV
            type_info (InfoResult): Type info
            put_info_type (PutInfoType): Whether override or create new

        Returns:
            OperationResult: The updated type info
        """
        LOG.info("Put type info for pv %s", pv)
        params = {"pv": pv}
        if put_info_type == PutInfoType.CreateNew:
            params["createnew"] = "true"
            params["override"] = "false"
        elif put_info_type == PutInfoType.Override:
            params["createnew"] = "false"
            params["override"] = "true"
        response = self._post(
            "/putPVTypeInfo",
            params=params,
            json=type_info,
        )
        result = cast("TypeInfo", response.json())
        LOG.debug("Put type info %s for pv %s", result, pv)
        return cast("TypeInfo", response.json())

    def get_policy_list(self) -> dict[str, str]:
        """Get the list of policies.

        Returns:
            dictionary of policies names and descriptions
        """
        r = self._get("/getPolicyList")
        return cast("dict[str, str]", r.json())
