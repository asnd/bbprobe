"""Tier-0 / Tier-1 gateways, interfaces, NAT (Policy API: ``/infra/tier-*``)."""

from __future__ import annotations

from .._client import NSXClient

TIER0 = "/infra/tier-0s"
TIER1 = "/infra/tier-1s"


def _gateway_base(tier: int) -> str:
    if tier == 0:
        return TIER0
    if tier == 1:
        return TIER1
    raise ValueError(f"tier must be 0 or 1, got {tier}")


def list_gateways(client: NSXClient, tier: int) -> list[dict]:
    return client.get_all(_gateway_base(tier))


def get_gateway(client: NSXClient, tier: int, gateway_id: str) -> dict:
    return client.policy_get(f"{_gateway_base(tier)}/{gateway_id}")


def create_gateway(client: NSXClient, tier: int, gateway_id: str, body: dict) -> dict:
    resource_type = "Tier0" if tier == 0 else "Tier1"
    payload = {"id": gateway_id, "resource_type": resource_type, **body}
    return client.policy_put(f"{_gateway_base(tier)}/{gateway_id}", payload)


def delete_gateway(client: NSXClient, tier: int, gateway_id: str) -> None:
    client.policy_delete(f"{_gateway_base(tier)}/{gateway_id}")


def gateway_should_be_realized(
    client: NSXClient, tier: int, gateway_id: str, *, timeout: float = 120.0, interval: float = 1.0
) -> list[dict]:
    return client.wait_for_realization(
        f"{_gateway_base(tier)}/{gateway_id}", timeout=timeout, interval=interval
    )


def list_locale_services(client: NSXClient, tier: int, gateway_id: str) -> list[dict]:
    return client.get_all(f"{_gateway_base(tier)}/{gateway_id}/locale-services")


def list_gateway_interfaces(client: NSXClient, tier: int, gateway_id: str) -> list[dict]:
    interfaces: list[dict] = []
    for ls in list_locale_services(client, tier, gateway_id):
        ls_id = ls.get("id")
        if not ls_id:
            continue
        interfaces.extend(
            client.get_all(f"{_gateway_base(tier)}/{gateway_id}/locale-services/{ls_id}/interfaces")
        )
    return interfaces


def list_nat_rules(client: NSXClient, tier: int, gateway_id: str) -> list[dict]:
    rules: list[dict] = []
    for ls in list_locale_services(client, tier, gateway_id):
        ls_id = ls.get("id")
        if not ls_id:
            continue
        rules.extend(
            client.get_all(
                f"{_gateway_base(tier)}/{gateway_id}/locale-services/{ls_id}/nat/rules"
            )
        )
    return rules


def nat_rule_should_be_realized(
    client: NSXClient,
    tier: int,
    gateway_id: str,
    rule_id: str,
    *,
    timeout: float = 120.0,
    interval: float = 1.0,
) -> list[dict]:
    base = _gateway_base(tier)
    for ls in list_locale_services(client, tier, gateway_id):
        ls_id = ls.get("id")
        if not ls_id:
            continue
        intent = f"{base}/{gateway_id}/locale-services/{ls_id}/nat/rules/{rule_id}"
        return client.wait_for_realization(intent, timeout=timeout, interval=interval)
    raise KeyError(f"no locale services on tier-{tier} gateway {gateway_id}")
