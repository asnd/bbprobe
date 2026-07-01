"""Edge/Gateway firewall (Policy API: gateway-policies under a domain).

A "gateway policy" is the NSX-T Policy object that scopes firewall rules to a
T0/T1 gateway via its ``scope`` field. Rules live under
``/infra/domains/<domain>/gateway-policies/<policy>/rules``.
"""

from __future__ import annotations

from .._client import NSXClient

DOMAINS = "/infra/domains"
DEFAULT_DOMAIN = "default"


def _policy_base(domain: str) -> str:
    return f"{DOMAINS}/{domain}/gateway-policies"


def list_gateway_policies(client: NSXClient, domain: str = DEFAULT_DOMAIN) -> list[dict]:
    return client.get_all(_policy_base(domain))


def get_gateway_policy(client: NSXClient, policy_id: str, domain: str = DEFAULT_DOMAIN) -> dict:
    return client.policy_get(f"{_policy_base(domain)}/{policy_id}")


def list_gateway_policy_rules(
    client: NSXClient, policy_id: str, domain: str = DEFAULT_DOMAIN
) -> list[dict]:
    return client.get_all(f"{_policy_base(domain)}/{policy_id}/rules")


def gateway_policy_rule_should_be_realized(
    client: NSXClient,
    policy_id: str,
    rule_id: str,
    domain: str = DEFAULT_DOMAIN,
    *,
    timeout: float = 120.0,
    interval: float = 1.0,
) -> list[dict]:
    intent = f"{_policy_base(domain)}/{policy_id}/rules/{rule_id}"
    return client.wait_for_realization(intent, timeout=timeout, interval=interval)
