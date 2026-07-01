"""Core HTTP client for VMware NSX-T 4.x (Policy + Manager REST APIs).

A single :class:`NSXClient` owns one ``requests.Session`` authenticated via
``POST /api/session/create`` (basic creds -> session cookie). It exposes thin
Policy (``/policy/api/v1``) and Manager (``/api/v1``) verbs, cursor paging,
async task polling, Policy realization-state waiting, retries on transient
failures, and structured error handling.

The Policy API is the primary, intent-based surface used by NSX-T 4.x; the
Manager API is only needed for live runtime state that Policy does not expose
(e.g. BGP/BFD neighbor session state, transport-node health).
"""

from __future__ import annotations

import time
from typing import Any

import requests
import urllib3
from requests.auth import HTTPBasicAuth

POLICY_BASE = "/policy/api/v1"
MANAGER_BASE = "/api/v1"

_RETRY_STATUSES = (429, 500, 502, 503, 504)


class NSXError(RuntimeError):
    """Structured NSX-T API error.

    Carries the HTTP status, the NSX ``error_code`` (when present), and the raw
    ``details`` payload so Robot keyword failures stay debuggable.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: int | None = None,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.details = details

    def __str__(self) -> str:
        base = super().__str__()
        parts = []
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.error_code is not None:
            parts.append(f"error_code={self.error_code}")
        return f"{base} ({', '.join(parts)})" if parts else base


class NSXClient:
    """Thin authenticated client over the NSX-T REST API."""

    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
        *,
        verify: bool = False,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 0.5,
        session: requests.Session | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.verify = verify
        self.timeout = timeout
        self.retries = max(0, retries)
        self.backoff = backoff
        self.session = session if session is not None else requests.Session()
        self.session.verify = verify
        self._connected = False
        if not verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> dict | None:
        """Authenticate via ``POST /api/session/create`` (basic auth -> cookie)."""
        if self._connected:
            return None
        if self.username is None or self.password is None:
            raise NSXError("connect requires username and password")
        resp = self._raw_request(
            "POST",
            f"{MANAGER_BASE}/session/create",
            auth=HTTPBasicAuth(self.username, self.password),
        )
        if resp.status_code not in (200, 201):
            self._raise_error(resp)
        self._connected = True
        try:
            return resp.json() if resp.text else None
        except ValueError:
            return None

    def disconnect(self) -> None:
        """Drop the session and close the underlying HTTP session."""
        if not self._connected:
            self.session.close()
            return
        try:
            self._raw_request("DELETE", f"{MANAGER_BASE}/session/create")
        except requests.RequestException:
            pass
        finally:
            self._connected = False
            self.session.close()

    def _raw_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        auth: Any = None,
        headers: dict | None = None,
    ) -> requests.Response:
        url = self.url + path
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    auth=auth,
                    headers=headers,
                    timeout=self.timeout,
                )
                if resp.status_code in _RETRY_STATUSES and attempt < self.retries:
                    time.sleep(self.backoff * (2**attempt))
                    continue
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(self.backoff * (2**attempt))
                    continue
                raise NSXError(f"request {method} {path} failed: {exc}") from exc
        assert last_exc is not None
        raise last_exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        base: str = POLICY_BASE,
        expect_json: bool = True,
        headers: dict | None = None,
    ) -> Any:
        resp = self._raw_request(
            method,
            base + path,
            params=params,
            json_body=json_body,
            headers=headers,
        )
        return self._handle(resp, expect_json)

    def _handle(self, resp: requests.Response, expect_json: bool) -> Any:
        if resp.status_code >= 400:
            self._raise_error(resp)
        if not expect_json:
            return None
        if not resp.text:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise NSXError(
                f"non-JSON response from {resp.request.method} {resp.request.url}",
                resp.status_code,
                details=resp.text,
            ) from exc

    def _raise_error(self, resp: requests.Response) -> None:
        try:
            body = resp.json()
        except ValueError:
            raise NSXError(
                resp.text or f"HTTP {resp.status_code}",
                resp.status_code,
            ) from None
        if isinstance(body, dict):
            msg = body.get("error_message") or body.get("message") or resp.text
            raise NSXError(
                msg or f"HTTP {resp.status_code}",
                resp.status_code,
                body.get("error_code"),
                body.get("details"),
            )
        raise NSXError(resp.text or f"HTTP {resp.status_code}", resp.status_code)

    def policy_get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params, base=POLICY_BASE)

    def policy_put(self, path: str, body: Any, *, headers: dict | None = None) -> Any:
        return self._request("PUT", path, json_body=body, base=POLICY_BASE, headers=headers)

    def policy_patch(self, path: str, body: Any, *, headers: dict | None = None) -> Any:
        return self._request("PATCH", path, json_body=body, base=POLICY_BASE, headers=headers)

    def policy_post(self, path: str, body: Any = None, *, params: dict | None = None) -> Any:
        return self._request("POST", path, params=params, json_body=body, base=POLICY_BASE)

    def policy_delete(self, path: str, params: dict | None = None) -> None:
        return self._request("DELETE", path, params=params, base=POLICY_BASE, expect_json=False)

    def manager_get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params, base=MANAGER_BASE)

    def manager_post(self, path: str, body: Any = None, *, params: dict | None = None) -> Any:
        return self._request("POST", path, params=params, json_body=body, base=MANAGER_BASE)

    def manager_delete(self, path: str, params: dict | None = None) -> None:
        return self._request("DELETE", path, params=params, base=MANAGER_BASE, expect_json=False)

    def get_all(
        self,
        path: str,
        *,
        params: dict | None = None,
        result_key: str = "results",
        cursor_param: str = "cursor",
        base: str = POLICY_BASE,
    ) -> list[dict]:
        """Page through a cursor-based collection until exhausted."""
        query = dict(params or {})
        out: list[dict] = []
        while True:
            page = self._request("GET", path, params=query, base=base)
            if page is None:
                break
            if isinstance(page, list):
                out.extend(page)
                break
            out.extend(page.get(result_key, []) or [])
            next_cursor = page.get(cursor_param)
            if not next_cursor or next_cursor == query.get(cursor_param):
                break
            query[cursor_param] = next_cursor
        return out

    def poll_task(
        self,
        task_id: str,
        *,
        interval: float = 1.0,
        timeout: float = 120.0,
    ) -> dict:
        """Poll a Manager async task until terminal status or timeout."""
        deadline = time.monotonic() + timeout
        last: dict = {}
        while True:
            last = self.manager_get(f"/tasks/{task_id}") or {}
            status = last.get("status", "").upper()
            if status == "COMPLETED":
                return last
            if status in ("FAILED", "CANCELED"):
                raise NSXError(
                    f"task {task_id} {status.lower()}",
                    details=last,
                )
            if time.monotonic() > deadline:
                raise NSXError(
                    f"task {task_id} timed out (last status={status or 'unknown'})",
                    details=last,
                )
            time.sleep(interval)

    def wait_for_realization(
        self,
        intent_path: str,
        *,
        timeout: float = 120.0,
        interval: float = 1.0,
    ) -> list[dict]:
        """Poll Policy realized-state for an intent path until REALIZED or ERROR.

        NSX-T Policy is declarative: a successful PUT only means the intent was
        accepted; the configuration is realized asynchronously. This blocks
        until every realized entity for ``intent_path`` reports ``REALIZED``.
        """
        deadline = time.monotonic() + timeout
        params = {"intent_path": intent_path, "enforce_revision_check": "true"}
        while True:
            data = self.policy_get("/infra/realized-state", params=params)
            results: list[dict] = []
            if isinstance(data, dict):
                results = data.get("results", []) or []
            elif isinstance(data, list):
                results = data
            if results:
                for entity in results:
                    state = (entity.get("state") or "").upper()
                    if state == "ERROR":
                        raise NSXError(
                            f"realization of {intent_path} failed",
                            details=entity,
                        )
                    if state != "REALIZED":
                        break
                else:
                    return results
            if time.monotonic() > deadline:
                states = ", ".join(
                    f"{e.get('entity_type','?')}={e.get('state','?')}" for e in results
                )
                raise NSXError(
                    f"realization of {intent_path} timed out ({states or 'no entities'})",
                    details=results,
                )
            time.sleep(interval)


def join_path(base: str, *parts: str) -> str:
    """Join NSX path segments, preserving a leading slash and flattening empties."""
    flat = "/".join(
        s for part in (base, *parts) if part is not None
        for s in str(part).strip("/").split("/") if s
    )
    return "/" + flat if flat else ""
