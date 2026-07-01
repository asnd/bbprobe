NSX_URL = "https://nsx.example.local"


def test_connect_and_disconnect(library, m):
    assert library.client.connected
    m.delete(f"{NSX_URL}/api/v1/session/create", status_code=200)
    library.disconnect_from_nsx()
    try:
        _ = library.client
    except AssertionError:
        return
    raise AssertionError("client should be None after disconnect")


def test_nsx_get(library, m):
    m.get(f"{NSX_URL}/policy/api/v1/infra/segments/web", json={"id": "web"})
    assert library.nsx_get("/infra/segments/web") == {"id": "web"}


def test_nsx_should_be_realized(library, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/realized-state",
        json={"results": [{"entity_type": "Segment", "state": "REALIZED"}]},
    )
    library.nsx_should_be_realized("/infra/segments/web", timeout="5")


def test_nsx_should_be_realized_failure_raises_assertion(library, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/realized-state",
        json={"results": [{"entity_type": "Segment", "state": "ERROR"}]},
    )
    try:
        library.nsx_should_be_realized("/infra/segments/web", timeout="5")
    except AssertionError:
        return
    raise AssertionError("expected AssertionError when realization ERROR")


def test_nsx_list_segments(library, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments",
        json={"results": [{"id": "web"}, {"id": "app"}]},
    )
    out = library.nsx_list_segments()
    assert [s["id"] for s in out] == ["web", "app"]


def test_nsx_create_segment(library, m):
    captured = {}

    def matcher(request, context):
        captured["body"] = request.json()
        context.status_code = 200
        return {"id": "web"}

    m.put(f"{NSX_URL}/policy/api/v1/infra/segments/web", json=matcher)
    library.nsx_create_segment("web", {"display_name": "web", "subnets": []})
    assert captured["body"]["id"] == "web"
    assert captured["body"]["resource_type"] == "Segment"


def test_nsx_segment_should_contain_vm_true(library, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments/web/ports",
        json={"results": [{"address_bindings": [{"vm_id": "vm-123"}]}]},
    )
    library.nsx_segment_should_contain_vm("web", "vm-123")


def test_nsx_segment_should_contain_vm_false_raises(library, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments/web/ports",
        json={"results": [{"address_bindings": [{"vm_id": "vm-999"}]}]},
    )
    try:
        library.nsx_segment_should_contain_vm("web", "vm-123")
    except AssertionError as exc:
        assert "vm-123" in str(exc)
    else:
        raise AssertionError("expected AssertionError when VM not on segment")


def test_nsx_gateway_should_be_realized(library, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/realized-state",
        json={"results": [{"entity_type": "Tier1", "state": "REALIZED"}]},
    )
    library.nsx_gateway_should_be_realized(1, "t1-a", timeout="5")


def test_nsx_bgp_neighbor_should_be_established(library, m):
    m.get(
        f"{NSX_URL}/api/v1/logical-routers/lr-1/routing/bgp/neighbors",
        json={"results": [{"neighbor_address": "10.0.0.1", "state": "ESTABLISHED"}]},
    )
    library.nsx_bgp_neighbor_should_be_established("lr-1", "10.0.0.1")


def test_nsx_bgp_neighbor_not_established_raises(library, m):
    m.get(
        f"{NSX_URL}/api/v1/logical-routers/lr-1/routing/bgp/neighbors",
        json={"results": [{"neighbor_address": "10.0.0.1", "state": "ACTIVE"}]},
    )
    try:
        library.nsx_bgp_neighbor_should_be_established("lr-1", "10.0.0.1")
    except AssertionError as exc:
        assert "ACTIVE" in str(exc)
    else:
        raise AssertionError("expected AssertionError on non-ESTABLISHED BGP neighbor")


def test_to_bool_helper():
    from nsx_robotframework.NSXLibrary import _to_bool

    assert _to_bool(True) is True
    assert _to_bool(False) is False
    assert _to_bool("true") is True
    assert _to_bool("False") is False
    assert _to_bool("${False}") is False
    assert _to_bool(None) is False
