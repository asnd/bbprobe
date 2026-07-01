from nsx_robotframework import NSXClient
from nsx_robotframework._client import NSXError, join_path

NSX_URL = "https://nsx.example.local"


def test_connect_sets_connected(m):
    m.post(f"{NSX_URL}/api/v1/session/create", json={}, status_code=200)
    c = NSXClient(NSX_URL, "admin", "pass", verify=False)
    assert not c.connected
    c.connect()
    assert c.connected


def test_connect_failure_raises_nsxerror(m):
    m.post(
        f"{NSX_URL}/api/v1/session/create",
        json={"error_code": 403, "error_message": "invalid credentials"},
        status_code=403,
    )
    c = NSXClient(NSX_URL, "admin", "bad", verify=False)
    try:
        c.connect()
    except NSXError as exc:
        assert exc.status_code == 403
        assert exc.error_code == 403
        assert "invalid credentials" in str(exc)
    else:
        raise AssertionError("expected NSXError on failed connect")


def test_policy_get(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments/web",
        json={"id": "web", "display_name": "web"},
    )
    data = client.policy_get("/infra/segments/web")
    assert data["id"] == "web"


def test_policy_put(client, m):
    captured = {}

    def matcher(request, context):
        captured["body"] = request.json()
        context.status_code = 200
        return {"id": "web"}

    m.put(f"{NSX_URL}/policy/api/v1/infra/segments/web", json=matcher)
    out = client.policy_put("/infra/segments/web", {"id": "web", "subnets": []})
    assert out["id"] == "web"
    assert captured["body"]["subnets"] == []


def test_policy_delete(client, m):
    m.delete(f"{NSX_URL}/policy/api/v1/infra/segments/web", status_code=200)
    assert client.policy_delete("/infra/segments/web") is None


def test_get_all_pages_cursor(client, m):
    page1 = {"results": [{"id": "a"}, {"id": "b"}], "cursor": "next1"}
    page2 = {"results": [{"id": "c"}], "cursor": None}
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments",
        [{"json": page1}, {"json": page2}],
    )
    out = client.get_all("/infra/segments")
    assert [r["id"] for r in out] == ["a", "b", "c"]


def test_get_all_single_list_response(client, m):
    m.get(f"{NSX_URL}/policy/api/v1/foo", json=[{"id": "x"}])
    out = client.get_all("/foo")
    assert out == [{"id": "x"}]


def test_poll_task_completed(client, m):
    m.get(
        f"{NSX_URL}/api/v1/tasks/task-1",
        [
            {"json": {"status": "IN_PROGRESS"}},
            {"json": {"status": "COMPLETED", "result": "ok"}},
        ],
    )
    result = client.poll_task("task-1", interval=0, timeout=5)
    assert result["result"] == "ok"


def test_poll_task_failed(client, m):
    m.get(f"{NSX_URL}/api/v1/tasks/task-2", json={"status": "FAILED"})
    try:
        client.poll_task("task-2", interval=0, timeout=5)
    except NSXError as exc:
        assert "task-2" in str(exc)
    else:
        raise AssertionError("expected NSXError on FAILED task")


def test_poll_task_timeout(client, m):
    m.get(f"{NSX_URL}/api/v1/tasks/task-3", json={"status": "IN_PROGRESS"})
    try:
        client.poll_task("task-3", interval=0, timeout=0.05)
    except NSXError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("expected timeout NSXError")


def test_wait_for_realization_realized(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/realized-state",
        [
            {"json": {"results": [{"entity_type": "Segment", "state": "UNREALIZED"}]}},
            {"json": {"results": [{"entity_type": "Segment", "state": "REALIZED"}]}},
        ],
    )
    out = client.wait_for_realization("/infra/segments/web", timeout=5, interval=0)
    assert out[0]["state"] == "REALIZED"


def test_wait_for_realization_error(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/realized-state",
        json={"results": [{"entity_type": "Segment", "state": "ERROR"}]},
    )
    try:
        client.wait_for_realization("/infra/segments/web", timeout=5, interval=0)
    except NSXError as exc:
        assert "realization" in str(exc)
    else:
        raise AssertionError("expected NSXError on ERROR realization")


def test_wait_for_realization_timeout(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/realized-state",
        json={"results": [{"entity_type": "Segment", "state": "UNREALIZED"}]},
    )
    try:
        client.wait_for_realization("/infra/segments/web", timeout=0.05, interval=0)
    except NSXError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("expected timeout NSXError")


def test_error_mapping_status_and_code(client, m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments/missing",
        json={"error_code": 5000, "error_message": "not found", "details": ["x"]},
        status_code=404,
    )
    try:
        client.policy_get("/infra/segments/missing")
    except NSXError as exc:
        assert exc.status_code == 404
        assert exc.error_code == 5000
        assert exc.details == ["x"]
        assert "not found" in str(exc)
    else:
        raise AssertionError("expected NSXError")


def test_retries_on_503_then_succeeds(m):
    m.get(
        f"{NSX_URL}/policy/api/v1/infra/segments",
        [{"status_code": 503}, {"json": {"results": []}}],
    )
    c = NSXClient(
        NSX_URL, "admin", "pass", verify=False, timeout=5, retries=2, backoff=0
    )
    m.post(f"{NSX_URL}/api/v1/session/create", json={}, status_code=200)
    c.connect()
    assert c.policy_get("/infra/segments") == {"results": []}


def test_manager_get_uses_api_base(client, m):
    m.get(
        f"{NSX_URL}/api/v1/logical-routers/lr-1/routing/bgp/neighbors",
        json={"results": [{"neighbor_address": "10.0.0.1", "state": "ESTABLISHED"}]},
    )
    out = client.manager_get("/logical-routers/lr-1/routing/bgp/neighbors")
    assert out["results"][0]["state"] == "ESTABLISHED"


def test_join_path():
    assert join_path("/infra", "segments", "seg") == "/infra/segments/seg"
    assert join_path("infra", "", "segments") == "/infra/segments"
    assert join_path("") == ""
