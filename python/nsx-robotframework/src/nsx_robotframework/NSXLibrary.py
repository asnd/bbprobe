"""Robot Framework library for VMware NSX-T 4.x.

    *** Settings ***
    Library    NSXLibrary

    *** Test Cases ***
    Segment Is Realized
        Connect To NSX    https://nsx.example.local    admin    ${PASS}
        NSX Wait For Realization    /infra/segments/web-seg    timeout=120s
        [Teardown]    Disconnect From NSX

Built as a thin wrapper over the NSX-T Policy (``/policy/api/v1``) and Manager
(``/api/v1``) REST APIs. See :class:`NSXClient` for the transport layer.
"""

from __future__ import annotations

from typing import Any

from robot.api.deco import keyword, library

from ._client import NSXClient, NSXError
from .domains import dhcp, edge_firewall, gateways, lb, routing, segments


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("true", "yes", "1", "on", "${true}")


def _to_int(value: Any, *, name: str = "value") -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _to_float(value: Any, *, default: float, name: str = "timeout") -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _realize(fn, *args, **kwargs):
    """Run a realization-wait helper, converting NSXError to a clean failure."""
    try:
        return fn(*args, **kwargs)
    except NSXError as exc:
        raise AssertionError(str(exc)) from exc


@library(scope="SUITE")
class NSXLibrary:
    """Robot Framework library keywords for NSX-T 4.x."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self, timeout: str = "30.0") -> None:
        self._default_timeout = _to_float(timeout, default=30.0)
        self._client: NSXClient | None = None

    @property
    def client(self) -> NSXClient:
        if self._client is None:
            raise AssertionError("not connected; call 'Connect To NSX' first")
        return self._client

    @keyword("Connect To NSX")
    def connect_to_nsx(
        self,
        url: str,
        username: str,
        password: str,
        verify: Any = "${False}",
        timeout: str = "",
    ) -> None:
        """Authenticate to NSX Manager via session create (basic auth -> cookie)."""
        self._client = NSXClient(
            url=url,
            username=username,
            password=password,
            verify=_to_bool(verify),
            timeout=_to_float(timeout, default=self._default_timeout),
        )
        try:
            self._client.connect()
        except NSXError as exc:
            self._client = None
            raise AssertionError(f"NSX connect failed: {exc}") from exc

    @keyword("Disconnect From NSX")
    def disconnect_from_nsx(self) -> None:
        if self._client is not None:
            self._client.disconnect()
            self._client = None

    @keyword("Set NSX Default Timeout")
    def set_default_timeout(self, timeout: str) -> None:
        self._default_timeout = _to_float(timeout, default=self._default_timeout)

    @keyword("NSX GET")
    def nsx_get(self, path: str) -> Any:
        """GET against the Policy API base (``/policy/api/v1``)."""
        return self.client.policy_get(path)

    @keyword("NSX Manager GET")
    def nsx_manager_get(self, path: str) -> Any:
        """GET against the Manager API base (``/api/v1``)."""
        return self.client.manager_get(path)

    @keyword("NSX PUT")
    def nsx_put(self, path: str, body: dict) -> Any:
        return self.client.policy_put(path, body)

    @keyword("NSX POST")
    def nsx_post(self, path: str, body: dict = None) -> Any:
        return self.client.policy_post(path, body)

    @keyword("NSX DELETE")
    def nsx_delete(self, path: str) -> None:
        return self.client.policy_delete(path)

    @keyword("NSX Poll Task")
    def nsx_poll_task(self, task_id: str, timeout: str = "120") -> dict:
        return self.client.poll_task(
            task_id, timeout=_to_float(timeout, default=120.0)
        )

    @keyword("NSX Wait For Realization")
    def nsx_wait_for_realization(self, intent_path: str, timeout: str = "120") -> list:
        """Block until every realized entity for ``intent_path`` is REALIZED."""
        return _realize(
            self.client.wait_for_realization,
            intent_path,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX Should Be Realized")
    def nsx_should_be_realized(self, intent_path: str, timeout: str = "120") -> None:
        _realize(
            self.client.wait_for_realization,
            intent_path,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX List Segments")
    def nsx_list_segments(self) -> list:
        return segments.list_segments(self.client)

    @keyword("NSX Get Segment")
    def nsx_get_segment(self, segment_id: str) -> dict:
        return segments.get_segment(self.client, segment_id)

    @keyword("NSX Create Segment")
    def nsx_create_segment(self, segment_id: str, body: dict) -> dict:
        return segments.create_segment(self.client, segment_id, body)

    @keyword("NSX Delete Segment")
    def nsx_delete_segment(self, segment_id: str) -> None:
        return segments.delete_segment(self.client, segment_id)

    @keyword("NSX Segment Should Be Realized")
    def nsx_segment_should_be_realized(self, segment_id: str, timeout: str = "120") -> None:
        _realize(
            segments.segment_should_be_realized,
            self.client,
            segment_id,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX List Segment Ports")
    def nsx_list_segment_ports(self, segment_id: str) -> list:
        return segments.list_segment_ports(self.client, segment_id)

    @keyword("NSX Segment Should Contain VM")
    def nsx_segment_should_contain_vm(self, segment_id: str, vm_id: str) -> None:
        _assert(
            segments.segment_contains_vm(self.client, segment_id, vm_id),
            f"segment {segment_id} does not contain VM {vm_id}",
        )

    @keyword("NSX List Gateways")
    def nsx_list_gateways(self, tier: Any) -> list:
        return gateways.list_gateways(self.client, _to_int(tier, name="tier"))

    @keyword("NSX Get Gateway")
    def nsx_get_gateway(self, tier: Any, gateway_id: str) -> dict:
        return gateways.get_gateway(self.client, _to_int(tier, name="tier"), gateway_id)

    @keyword("NSX Create Gateway")
    def nsx_create_gateway(self, tier: Any, gateway_id: str, body: dict) -> dict:
        return gateways.create_gateway(self.client, _to_int(tier, name="tier"), gateway_id, body)

    @keyword("NSX Delete Gateway")
    def nsx_delete_gateway(self, tier: Any, gateway_id: str) -> None:
        return gateways.delete_gateway(self.client, _to_int(tier, name="tier"), gateway_id)

    @keyword("NSX Gateway Should Be Realized")
    def nsx_gateway_should_be_realized(
        self, tier: Any, gateway_id: str, timeout: str = "120"
    ) -> None:
        _realize(
            gateways.gateway_should_be_realized,
            self.client,
            _to_int(tier, name="tier"),
            gateway_id,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX List Gateway Interfaces")
    def nsx_list_gateway_interfaces(self, tier: Any, gateway_id: str) -> list:
        return gateways.list_gateway_interfaces(self.client, _to_int(tier, name="tier"), gateway_id)

    @keyword("NSX List NAT Rules")
    def nsx_list_nat_rules(self, tier: Any, gateway_id: str) -> list:
        return gateways.list_nat_rules(self.client, _to_int(tier, name="tier"), gateway_id)

    @keyword("NSX NAT Rule Should Be Realized")
    def nsx_nat_rule_should_be_realized(
        self, tier: Any, gateway_id: str, rule_id: str, timeout: str = "120"
    ) -> None:
        _realize(
            gateways.nat_rule_should_be_realized,
            self.client,
            _to_int(tier, name="tier"),
            gateway_id,
            rule_id,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX List Gateway Firewall Policies")
    def nsx_list_gateway_firewall_policies(self, domain: str = "default") -> list:
        return edge_firewall.list_gateway_policies(self.client, domain)

    @keyword("NSX List Gateway Firewall Rules")
    def nsx_list_gateway_firewall_rules(self, policy_id: str, domain: str = "default") -> list:
        return edge_firewall.list_gateway_policy_rules(self.client, policy_id, domain)

    @keyword("NSX Gateway Firewall Rule Should Be Realized")
    def nsx_gateway_firewall_rule_should_be_realized(
        self, policy_id: str, rule_id: str, domain: str = "default", timeout: str = "120"
    ) -> None:
        _realize(
            edge_firewall.gateway_policy_rule_should_be_realized,
            self.client,
            policy_id,
            rule_id,
            domain,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX List BGP Neighbors")
    def nsx_list_bgp_neighbors(self, gateway_id: str, locale_service_id: str) -> list:
        return routing.list_bgp_neighbors(self.client, gateway_id, locale_service_id)

    @keyword("NSX List BFD Peers")
    def nsx_list_bfd_peers(self, gateway_id: str, locale_service_id: str) -> list:
        return routing.list_bfd_peers(self.client, gateway_id, locale_service_id)

    @keyword("NSX List Static Routes")
    def nsx_list_static_routes(
        self, tier: Any, gateway_id: str, locale_service_id: str
    ) -> list:
        return routing.list_static_routes(
            self.client, _to_int(tier, name="tier"), gateway_id, locale_service_id
        )

    @keyword("NSX BGP Neighbor Should Be Realized")
    def nsx_bgp_neighbor_should_be_realized(
        self, gateway_id: str, locale_service_id: str, neighbor_id: str, timeout: str = "120"
    ) -> None:
        _realize(
            routing.bgp_neighbor_should_be_realized,
            self.client,
            gateway_id,
            locale_service_id,
            neighbor_id,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX BGP Neighbor Should Be Established")
    def nsx_bgp_neighbor_should_be_established(
        self, logical_router_id: str, neighbor_ip: str
    ) -> None:
        neighbors = routing.get_logical_router_bgp_neighbors(self.client, logical_router_id)
        match = [n for n in neighbors if n.get("neighbor_address") == neighbor_ip]
        _assert(
            bool(match),
            f"no BGP neighbor {neighbor_ip} on logical-router {logical_router_id}",
        )
        state = (match[0].get("state") or "").upper()
        _assert(
            state == "ESTABLISHED",
            f"BGP neighbor {neighbor_ip} state is {state or 'unknown'} (expected ESTABLISHED)",
        )

    @keyword("NSX BFD Session Should Be Up")
    def nsx_bfd_session_should_be_up(self, logical_router_id: str, peer_address: str) -> None:
        sessions = routing.get_logical_router_bfd_sessions(self.client, logical_router_id)
        match = [s for s in sessions if s.get("peer_address") == peer_address]
        _assert(
            bool(match),
            f"no BFD session to {peer_address} on logical-router {logical_router_id}",
        )
        state = (match[0].get("state") or "").upper()
        _assert(state == "UP", f"BFD session {peer_address} state is {state or 'unknown'} (expected UP)")

    @keyword("NSX List LB Virtual Servers")
    def nsx_list_lb_virtual_servers(self) -> list:
        return lb.list_lb_virtual_servers(self.client)

    @keyword("NSX List LB Pools")
    def nsx_list_lb_pools(self) -> list:
        return lb.list_lb_pools(self.client)

    @keyword("NSX List LB Services")
    def nsx_list_lb_services(self) -> list:
        return lb.list_lb_services(self.client)

    @keyword("NSX LB Virtual Server Should Be Realized")
    def nsx_lb_virtual_server_should_be_realized(
        self, vs_id: str, timeout: str = "120"
    ) -> None:
        _realize(
            lb.lb_virtual_server_should_be_realized,
            self.client,
            vs_id,
            timeout=_to_float(timeout, default=120.0),
        )

    @keyword("NSX List DHCP Static Bindings")
    def nsx_list_dhcp_static_bindings(self, segment_id: str) -> list:
        return dhcp.list_dhcp_static_bindings(self.client, segment_id)

    @keyword("NSX List DHCP Server Profiles")
    def nsx_list_dhcp_server_profiles(self) -> list:
        return dhcp.list_dhcp_server_profiles(self.client)

    @keyword("NSX DHCP Server Profile Should Be Realized")
    def nsx_dhcp_server_profile_should_be_realized(
        self, profile_id: str, timeout: str = "120"
    ) -> None:
        _realize(
            dhcp.dhcp_server_profile_should_be_realized,
            self.client,
            profile_id,
            timeout=_to_float(timeout, default=120.0),
        )
