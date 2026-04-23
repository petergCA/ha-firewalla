"""Dataclasses representing Firewalla MSP API objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Group:
    id: str
    name: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Group:
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
        )


@dataclass
class Target:
    type: str
    value: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Target:
        return cls(
            type=str(d.get("type", "")),
            value=str(d.get("value", "")),
        )


@dataclass
class Scope:
    type: str
    value: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Scope:
        return cls(
            type=str(d.get("type", "")),
            value=str(d.get("value", "")),
        )


@dataclass
class Box:
    gid: str
    name: str | None
    model: str
    online: bool
    version: str | None
    device_count: int
    rule_count: int
    alarm_count: int
    public_ip: str | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Box:
        return cls(
            gid=str(d.get("gid", "")),
            name=d.get("name") or None,
            model=str(d.get("model", "Unknown")),
            online=bool(d.get("online", False)),
            version=d.get("version") or d.get("firmware") or None,
            device_count=int(d.get("deviceCount", d.get("device_count", 0))),
            rule_count=int(d.get("ruleCount", d.get("rule_count", 0))),
            alarm_count=int(d.get("alarmCount", d.get("alarm_count", 0))),
            public_ip=d.get("publicIp", d.get("public_ip")) or None,
        )


@dataclass
class Device:
    id: str
    name: str | None
    online: bool
    ip: str | None
    mac_vendor: str | None
    network_name: str | None
    group: Group | None
    total_download: int | None
    total_upload: int | None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Device:
        raw_group = d.get("group")
        group = Group.from_dict(raw_group) if isinstance(raw_group, dict) and raw_group.get("id") else None

        raw_network = d.get("network")
        network_name: str | None = None
        if isinstance(raw_network, dict):
            network_name = raw_network.get("name") or None
        elif isinstance(raw_network, str):
            network_name = raw_network or None

        return cls(
            id=str(d.get("id", d.get("mac", ""))),
            name=d.get("name") or None,
            online=bool(d.get("online", False)),
            ip=d.get("ip") or d.get("ipv4") or None,
            mac_vendor=d.get("macVendor", d.get("mac_vendor")) or None,
            network_name=network_name,
            group=group,
            total_download=_to_int(d.get("download", d.get("totalDownload", d.get("total_download")))),
            total_upload=_to_int(d.get("upload", d.get("totalUpload", d.get("total_upload")))),
        )


@dataclass
class Rule:
    id: str
    notes: str
    action: str
    direction: str
    target: Target | None
    scope: Scope | None
    _status: str = field(repr=False)

    @property
    def is_active(self) -> bool:
        return self._status == "active"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Rule:
        raw_target = d.get("target")
        target = Target.from_dict(raw_target) if isinstance(raw_target, dict) else None

        raw_scope = d.get("scope")
        scope = Scope.from_dict(raw_scope) if isinstance(raw_scope, dict) else None

        # "active" when status field says so, or when there's no "paused" flag set
        status = str(d.get("status", "active"))
        if d.get("paused", False):
            status = "paused"

        return cls(
            id=str(d.get("id", d.get("rid", ""))),
            notes=str(d.get("notes", d.get("description", ""))),
            action=str(d.get("action", "block")),
            direction=str(d.get("direction", "bidirection")),
            target=target,
            scope=scope,
            _status=status,
        )


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
