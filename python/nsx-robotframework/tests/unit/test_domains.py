from nsx_robotframework.domains import dhcp, edge_firewall, gateways, lb, routing, segments

NSX_URL = "https://nsx.example.local"


def test_segments_create_and_get(client, m):
    def put_matcher(request, context):
        body = request.json()
        context.status_code = 200
        return body

    m.put(f"{NSX_URL}/policy/api/v1/infra/segments/web", json=put_matcher)
    out = segments.create_segment(client, "web", {"display_name": "web"})
    assert out["id"] == "web"
    assert out["resource_type"] == "Segment"

    m.get(f"{NSX_URL}/policy/api/v1/infra/segments/web", json={"id": "web"})
    assert segments.get_segment(client, "web")["id"] == "web"


def test_segments_contains_vm(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments/web/ports",
        json={
            "results": [
                {"attachment": {"id": "other"}, "address_bindings": []},
                {"address_bindings": [{"vm_id": "vm-7"}]},
            ]
        },
    )
    assert segments.segment_contains_vm(client, "web", "vm-7") is True
    assert segments.segment_contains_vm(client, "web", "vm-99") is False


def test_gateways_locale_services_and_nat(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/tier-1s/t1-a/locale-services",
        json={"results": [{"id": "ls-1"}]},
    )
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/tier-1s/t1-a/locale-services/ls-1/nat/rules",
        json={"results": [{"id": "snat-1"}]},
    )
    rules = gateways.list_nat_rules(client, 1, "t1-a")
    assert [r["id"] for r in rules] == ["snat-1"]


def test_gateways_interfaces_across_locale_services(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/tier-0s/t0-x/locale-services",
        json={"results": [{"id": "ls-1"}, {"id": "ls-2"}]},
    )
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/tier-0s/t0-x/locale-services/ls-1/interfaces",
        json={"results": [{"id": "if-1"}]},
    )
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/tier-0s/t0-x/locale-services/ls-2/interfaces",
        json={"results": [{"id": "if-2"}]},
    )
    ifs = gateways.list_gateway_interfaces(client, 0, "t0-x")
    assert [i["id"] for i in ifs] == ["if-1", "if-2"]


def test_edge_firewall_rules(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/domains/default/gateway-policies",
        json={"results": [{"id": "gw-fw", "scope": ["/infra/tier-1s/t1-a"]}]},
    )
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/domains/default/gateway-policies/gw-fw/rules",
        json={"results": [{"id": "rule-1", "action": "ALLOW"}]},
    )
    pols = edge_firewall.list_gateway_policies(client)
    assert pols[0]["id"] == "gw-fw"
    rules = edge_firewall.list_gateway_policy_rules(client, "gw-fw")
    assert rules[0]["action"] == "ALLOW"


def test_routing_static_routes(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/tier-0s/t0-x/locale-services/ls-1/static-routes",
        json={"results": [{"id": "rt-1", "network": "10.0.0.0/24"}]},
    )
    out = routing.list_static_routes(client, 0, "t0-x", "ls-1")
    assert out[0]["network"] == "10.0.0.0/24"


def test_routing_manager_bfd_sessions(client, m):
    m.get(
        f"{NSX_URL}/api/v1/logical-routers/lr-1/routing/bfd/sessions",
        json={"results": [{"peer_address": "10.0.0.2", "state": "UP"}]},
    )
    sessions = routing.get_logical_router_bfd_sessions(client, "lr-1")
    assert sessions[0]["state"] == "UP"


def test_lb_virtual_servers(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/lb-virtual-servers",
        json={"results": [{"id": "vs-1", "ip_address": "10.0.0.10"}]},
    )
    out = lb.list_lb_virtual_servers(client)
    assert out[0]["id"] == "vs-1"


def test_dhcp_static_bindings(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments/web/dhcp-static-binding-mappings",
        json={"results": [{"id": "b-1", "ip_address": "10.0.0.5"}]},
    )
    out = dhcp.list_dhcp_static_bindings(client, "web")
    assert out[0]["ip_address"] == "10.0.0.5"


def test_routing_first_locale_service(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/tier-0s/t0-x/locale-services",
        json={"results": [{"id": "ls-9"}]},
    )
    assert routing.first_locale_service(client, "t0-x") == "ls-9"
