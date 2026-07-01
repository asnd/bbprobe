"""Routing: BGP/BFD config (Policy) + live session state (Manager escape hatch).

Policy intent (config) lives under
``/infra/tier-0s/<t0>/locale-services/<ls>/bgp[/neighbors]`` and ``.../bfd``.

Live runtime state (neighbor session ``ESTABLISHED``/``ACTIVE``, BFD ``UP``) is
NOT exposed by Policy -- it lives on the Manager API under
``/api/v1/logical-routers/<lr-id>/routing/{bgp,bfd}``. Mapping a tier-0 Policy
id to a logical-router Manager id is the caller's responsibility for now; a
helper can be added once validated against a real 4.1 lab.
"""

from __future__ import annotations

from .._client import NSXClient
from .gateways import TIER0, list_locale_services

TIER = 0


def list_bgp_neighbors(client: NSXClient, gateway_id: str, locale_service_id: str) -> list[dict]:
    base = f"{TIER0}/{gateway_id}/locale-services/{locale_service_id}/bgp/neighbors"
    return client.get_all(base)


def get_bgp_config(client: NSXClient, gateway_id: str, locale_service_id: str) -> dict:
    return client.policy_get(
        f"{TIER0}/{gateway_id}/locale-services/{locale_service_id}/bgp"
    )


def create_bgp_neighbor(
    client: NSXClient, gateway_id: str, locale_service_id: str, neighbor_id: str, body: dict
) -> dict:
    base = f"{TIER0}/{gateway_id}/locale-services/{locale_service_id}/bgp/neighbors/{neighbor_id}"
    payload = {"id": neighbor_id, "resource_type": "BgpNeighbor", **body}
    return client.policy_put(base, payload)


def bgp_neighbor_should_be_realized(
    client: NSXClient,
    gateway_id: str,
    locale_service_id: str,
    neighbor_id: str,
    *,
    timeout: float = 120.0,
    interval: float = 1.0,
) -> list[dict]:
    intent = (
        f"{TIER0}/{gateway_id}/locale-services/{locale_service_id}/bgp/neighbors/{neighbor_id}"
    )
    return client.wait_for_realization(intent, timeout=timeout, interval=interval)


def list_bfd_peers(client: NSXClient, gateway_id: str, locale_service_id: str) -> list[dict]:
    base = f"{TIER0}/{gateway_id}/locale-services/{locale_service_id}/bfd/peers"
    return client.get_all(base)


def list_static_routes(
    client: NSXClient, tier: int, gateway_id: str, locale_service_id: str
) -> list[dict]:
    from .gateways import _gateway_base

    base = (
        f"{_gateway_base(tier)}/{gateway_id}/locale-services/{locale_service_id}/static-routes"
    )
    return client.get_all(base)


def get_logical_router_bgp_neighbors(
    client: NSXClient, logical_router_id: str
) -> list[dict]:
    """Manager API: live BGP neighbor runtime state (``state``, ``uptime``...)."""
    return client.manager_get(
        f"/logical-routers/{logical_router_id}/routing/bgp/neighbors"
    ).get("results", [])


def get_logical_router_bfd_sessions(
    client: NSXClient, logical_router_id: str
) -> list[dict]:
    """Manager API: live BFD session runtime state (``state``=UP/DOWN/...)."""
    return client.manager_get(
        f"/logical-routers/{logical_router_id}/routing/bfd/sessions"
    ).get("results", [])


def first_locale_service(client: NSXClient, gateway_id: str) -> str:
    """Return the id of the first locale service on a tier-0 gateway."""
    for ls in list_locale_services(client, TIER, gateway_id):
        if ls.get("id"):
            return ls["id"]
    raise KeyError(f"no locale services on tier-0 gateway {gateway_id}")
