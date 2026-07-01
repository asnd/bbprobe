"""DHCP: static bindings, server profiles, relay (Policy API)."""

from __future__ import annotations

from .._client import NSXClient
from .segments import SEGMENTS

DHCP_SERVER_PROFILES = "/infra/dhcp-server-profiles"
DHCP_RELAY_CONFIGS = "/infra/dhcp-relay-configs"


def list_dhcp_static_bindings(client: NSXClient, segment_id: str) -> list[dict]:
    return client.get_all(f"{SEGMENTS}/{segment_id}/dhcp-static-binding-mappings")


def list_dhcp_server_profiles(client: NSXClient) -> list[dict]:
    return client.get_all(DHCP_SERVER_PROFILES)


def get_dhcp_server_profile(client: NSXClient, profile_id: str) -> dict:
    return client.policy_get(f"{DHCP_SERVER_PROFILES}/{profile_id}")


def list_dhcp_relay_configs(client: NSXClient) -> list[dict]:
    return client.get_all(DHCP_RELAY_CONFIGS)


def dhcp_server_profile_should_be_realized(
    client: NSXClient, profile_id: str, *, timeout: float = 120.0, interval: float = 1.0
) -> list[dict]:
    return client.wait_for_realization(
        f"{DHCP_SERVER_PROFILES}/{profile_id}", timeout=timeout, interval=interval
    )
