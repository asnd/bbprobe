# nsx-robotframework

A [Robot Framework](https://robotframework.org) library for **VMware NSX-T 4.x**,
built as a thin wrapper over the NSX-T Policy (`/policy/api/v1`) and Manager
(`/api/v1`) REST APIs.

There is no existing Robot Framework library for NSX-T (RPA Framework, GitHub,
and PyPI were all checked). This package fills that gap with a deliberately
small, version-agnostic surface: one authenticated `requests.Session` and one
keyword per common operation, plus the two helpers every Policy test needs —
async task polling and intent realization-state waiting.

## Install

```sh
pip install nsx-robotframework
```

For development:

```sh
pip install -e .[dev]     # adds pytest, requests_mock, ruff
```

## Usage

```robotframework
*** Settings ***
Library    NSXLibrary

*** Test Cases ***
Web Segment Is Realized And Carries The App VM
    Connect To NSX    https://nsx.example.local    admin    ${PASS}
    ...                verify=${FALSE}
    NSX Segment Should Be Realized    web    timeout=120
    NSX Segment Should Contain VM     web    vm-123
    [Teardown]    Disconnect From NSX

BGP To Spine Is Established
    Connect To NSX    https://nsx.example.local    admin    ${PASS}
    NSX BGP Neighbor Should Be Established    lr-1    10.0.0.1
    [Teardown]    Disconnect From NSX
```

`Connect To NSX` authenticates via `POST /api/session/create` (basic auth →
session cookie). All subsequent keywords reuse that cookie.

## Architecture

- `_client.py` — `NSXClient`: one `requests.Session`; Policy + Manager verbs;
  cursor paging; async-task polling; **Policy realization-state waiting**
  (the lynchpin for intent-based asserts); retries on 429/5xx; structured
  `NSXError` (carries `status_code`, `error_code`, `details`).
- `NSXLibrary.py` — Robot façade; `@keyword`-decorated methods grouped by
  domain. Assertion keywords (`... Should Be ...`) raise `AssertionError` on
  failure, so Robot reports them as clean test failures, not exceptions.
- `domains/` — one module per Policy area: `segments`, `gateways`
  (T0/T1, interfaces, NAT), `edge_firewall` (gateway policies/rules),
  `routing` (BGP/BFD config via Policy + **live session state via Manager**),
  `lb` (T1 virtual servers/pools/services), `dhcp` (static bindings/profiles).

### Policy vs Manager

NSX-T Policy is declarative — a successful `PUT` only means the intent was
accepted; the configuration is realized asynchronously. Two consequences drive
the design:

1. `NSX Wait For Realization` / `... Should Be Realized` poll
   `GET /infra/realized-state?intent_path=...` until every realized entity
   reports `REALIZED`.
2. Live runtime state that Policy does not expose (BGP neighbor `ESTABLISHED`,
   BFD `UP`) lives on the **Manager** API under
   `/api/v1/logical-routers/<id>/routing/{bgp,bfd}`. Those keywords take a
   logical-router id directly; mapping a tier-0 Policy id to a logical-router
   id is a later helper (validated against a real 4.1 lab).

## Keyword reference

| Area | Keywords |
|------|----------|
| Session | `Connect To NSX`, `Disconnect From NSX`, `Set NSX Default Timeout` |
| Generic | `NSX GET`, `NSX PUT`, `NSX POST`, `NSX DELETE`, `NSX Manager GET`, `NSX Poll Task`, `NSX Wait For Realization`, `NSX Should Be Realized` |
| Segments | `NSX List Segments`, `NSX Get Segment`, `NSX Create Segment`, `NSX Delete Segment`, `NSX Segment Should Be Realized`, `NSX List Segment Ports`, `NSX Segment Should Contain VM` |
| Gateways | `NSX List Gateways`, `NSX Get Gateway`, `NSX Create Gateway`, `NSX Delete Gateway`, `NSX Gateway Should Be Realized`, `NSX List Gateway Interfaces`, `NSX List NAT Rules`, `NSX NAT Rule Should Be Realized` |
| Edge FW | `NSX List Gateway Firewall Policies`, `NSX List Gateway Firewall Rules`, `NSX Gateway Firewall Rule Should Be Realized` |
| Routing | `NSX List BGP Neighbors`, `NSX List BFD Peers`, `NSX List Static Routes`, `NSX BGP Neighbor Should Be Realized`, `NSX BGP Neighbor Should Be Established`, `NSX BFD Session Should Be Up` |
| LB | `NSX List LB Virtual Servers`, `NSX List LB Pools`, `NSX List LB Services`, `NSX LB Virtual Server Should Be Realized` |
| DHCP | `NSX List DHCP Static Bindings`, `NSX List DHCP Server Profiles`, `NSX DHCP Server Profile Should Be Realized` |

## Testing

The suites run fully mocked — no NSX-T lab required.

- `tests/unit/` — `requests_mock`-based tests for the client, library, and
  every domain (39 tests).
- `tests/robot/` — an in-process fake NSX HTTP server (`tests/robot/lib/FakeNSX.py`)
  powers an end-to-end Robot suite (10 tests) covering connect, segments,
  realization, BGP state, LB, and the generic verbs.

```sh
make nsxlib-lint    # ruff
make nsxlib-test    # pytest + robot
make nsxlib-build   # sdist + wheel
```

Override the interpreter with `NSX_PY=/path/to/python` if you are not using
the default venv.

## Scope and status

v0.1.0 covers the foundation and the eight Policy domains at the common-CRUD +
realization level. Deeper sub-resources (every LB profile variant, exhaustive
BGP timers, DHCP relay server-fault modes) and the tier-0→logical-router id
mapping are deferred until validation against a real NSX-T 4.1 lab.
