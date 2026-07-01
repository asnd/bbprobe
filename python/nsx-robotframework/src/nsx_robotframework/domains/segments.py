"""Segments and segment ports (Policy API: ``/infra/segments``)."""

from __future__ import annotations

from .._client import NSXClient

SEGMENTS = "/infra/segments"


def list_segments(client: NSXClient) -> list[dict]:
    return client.get_all(SEGMENTS)


def get_segment(client: NSXClient, segment_id: str) -> dict:
    return client.policy_get(f"{SEGMENTS}/{segment_id}")


def create_segment(client: NSXClient, segment_id: str, body: dict) -> dict:
    payload = {"id": segment_id, "resource_type": "Segment", **body}
    return client.policy_put(f"{SEGMENTS}/{segment_id}", payload)


def delete_segment(client: NSXClient, segment_id: str) -> None:
    client.policy_delete(f"{SEGMENTS}/{segment_id}")


def segment_should_be_realized(
    client: NSXClient, segment_id: str, *, timeout: float = 120.0, interval: float = 1.0
) -> list[dict]:
    return client.wait_for_realization(
        f"{SEGMENTS}/{segment_id}", timeout=timeout, interval=interval
    )


def list_segment_ports(client: NSXClient, segment_id: str) -> list[dict]:
    return client.get_all(f"{SEGMENTS}/{segment_id}/ports")


def segment_contains_vm(client: NSXClient, segment_id: str, vm_id: str) -> bool:
    """True if any segment port's address_bindings reference ``vm_id``.

    ``vm_id`` is the vSphere moref (e.g. ``vm-123``) that NSX records in each
    port's ``address_bindings[].vm_id`` when a VM vNIC attaches to the segment.
    """
    for port in list_segment_ports(client, segment_id):
        for binding in port.get("address_bindings", []) or []:
            if binding.get("vm_id") == vm_id:
                return True
        if port.get("attachment", {}).get("id") == vm_id:
            return True
    return False
