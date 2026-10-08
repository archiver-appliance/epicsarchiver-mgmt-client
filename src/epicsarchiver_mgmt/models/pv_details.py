"""Handles the PVDetails report per PV from the Archiver."""

from __future__ import annotations

from collections import UserDict
from enum import StrEnum


class DetailEnum(StrEnum):
    """Enum of detail types present in the archiver per PV."""

    PVName = "PV Name"
    DBRType = "Archiver DBR type (from typeinfo):"
    PVAccess = "Are we using PVAccess?"
    Method = "Sampling method:"
    Period = "Sampling period:"
    Capacity = "Sample buffer capacity"
    EventRate = "Estimated event rate (events/sec)"
    EventsLost = "How many events lost totally so far?"
    TotalEvents = "How many events so far?"
    Connected = "Is this PV currently connected?"
    LastLostConnection = "When did we last lose a connection to this PV?"
    LostConnections = "How many times have we lost and regained the connection to this PV?"
    LostEventsTimestamp = "How many events lost because the timestamp is in the far future or past so far?"
    LostEventsBuffer = "How many events lost because the sample buffer is full so far?"
    LostEventsType = "How many events lost because the DBR_Type of the PV has changed from what it used to be?"
    MBStorageRate = "Estimated storage rate (MB/day)"
    LastEvent = "When did we receive the last event?"
    Hostname = "Hostname of PV from CA"
    Instance = "Instance archiving PV"
    CommandThread = "The CAJ command thread id"

    @classmethod
    def from_str(cls, desc: str) -> DetailEnum | None:
        """Convert from a string to DetailEnum.

        Args:
            desc (str): input string

        Returns:
            DetailEnum | None: An enum representation.
        """
        for e in DetailEnum:
            if e.value == desc:
                return e
        return None


class Details(UserDict[DetailEnum, str]):
    """Representation of the response from the pvDetails endpoint in archiver."""

    @classmethod
    def from_json(cls, json: list[dict[str, str]]) -> Details:
        """Convert from the json representation at the Archiver Endpoint.

        Takes some of the details which are relevant for reports to create Details.

        Args:
            json (list[dict[str, str]]): input json

        Returns:
            Details: dictionary of DetailEnum to string value.
        """
        result: Details = Details()
        for json_det in json:
            detail_enum = DetailEnum.from_str(json_det["name"])
            if detail_enum:
                result[detail_enum] = json_det["value"]
        return result
