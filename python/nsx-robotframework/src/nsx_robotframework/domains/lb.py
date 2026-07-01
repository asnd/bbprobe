"""Tier-1 load balancer (Policy API: ``/infra/lb-*``).

Policy LB objects are global under ``/infra`` and reference a tier-1 gateway
through the LB service (``/infra/lb-services/<id>``) and pool/virtual-server
paths. Realization state is fetched the same way as every other Policy intent.
"""

from __future__ import annotations

from .._client import NSXClient

LB_VIRTUAL_SERVERS = "/infra/lb-virtual-servers"
LB_POOLS = "/infra/lb-pools"
LB_SERVICES = "/infra/lb-services"
LB_MONITORS = "/infra/lb-monitor-profiles"


def list_lb_virtual_servers(client: NSXClient) -> list[dict]:
    return client.get_all(LB_VIRTUAL_SERVERS)


def get_lb_virtual_server(client: NSXClient, vs_id: str) -> dict:
    return client.policy_get(f"{LB_VIRTUAL_SERVERS}/{vs_id}")


def list_lb_pools(client: NSXClient) -> list[dict]:
    return client.get_all(LB_POOLS)


def get_lb_pool(client: NSXClient, pool_id: str) -> dict:
    return client.policy_get(f"{LB_POOLS}/{pool_id}")


def list_lb_services(client: NSXClient) -> list[dict]:
    return client.get_all(LB_SERVICES)


def list_lb_monitors(client: NSXClient) -> list[dict]:
    return client.get_all(LB_MONITORS)


def lb_virtual_server_should_be_realized(
    client: NSXClient, vs_id: str, *, timeout: float = 120.0, interval: float = 1.0
) -> list[dict]:
    return client.wait_for_realization(
        f"{LB_VIRTUAL_SERVERS}/{vs_id}", timeout=timeout, interval=interval
    )


def lb_service_should_be_realized(
    client: NSXClient, service_id: str, *, timeout: float = 120.0, interval: float = 1.0
) -> list[dict]:
    return client.wait_for_realization(
        f"{LB_SERVICES}/{service_id}", timeout=timeout, interval=interval
    )
