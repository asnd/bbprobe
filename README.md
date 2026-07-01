# bbprobe

A single-shot, **agentless** network-probe CLI. It is pushed to client-emulating
VMs and invoked **once per test over SSH**:

```sh
ssh vm 'bbprobe --module icmp --target 10.0.0.1'
```

`bbprobe` runs one or more [Prometheus blackbox_exporter][bb] probes (`http`,
`tcp`, `icmp`, `dns`, `grpc`, `unix`), prints a structured JSON (or Prometheus
text) result to **stdout**, and exits with a code the test harness can assert on.

- No daemon, no listening port, no root.
- Reuses the **actual** blackbox_exporter probe implementations as a library
  (pinned to `v0.28.0`) — the probes are **not** reimplemented.
- Ships an embedded default config, so it works with no `--config`.

[bb]: https://github.com/prometheus/blackbox_exporter

## Build

Requires Go >= 1.24.

```sh
make build            # native static binary ./bbprobe (CGO disabled)
make cross            # dist/bbprobe-{linux-amd64,linux-arm64,darwin-arm64}
make test             # unit tests
make vet              # go vet
```

The binary is static (`CGO_ENABLED=0`); verify with:

```sh
file dist/bbprobe-linux-amd64      # ... statically linked ...
ldd  dist/bbprobe-linux-amd64      # not a dynamic executable
```

Version/commit are injected via ldflags (`make ... VERSION=v1.0.0`).

## Flags

| Flag        | Default | Description |
|-------------|---------|-------------|
| `--module`  | —       | **Required.** Comma-separated module name(s), e.g. `http_2xx,icmp`. |
| `--target`  | —       | **Required.** Probe target: URL, host, or IP. |
| `--dst`     | —       | Alias for `--target` (destination host/IP/FQDN). |
| `--config`  | *embedded* | Path to a `blackbox.yml`. Omit to use the built-in config. |
| `--timeout` | `10s`   | Per-attempt probe timeout (wraps each probe in a context deadline). |
| `--format`  | `json`  | `json` or `prom` (Prometheus text exposition). |
| `--repeat`  | `1`     | Number of attempts per module. |
| `--debug`   | `false` | Include the prober's debug plaintext in the JSON result. |
| `--version` | —       | Print version/commit and exit. |

### Embedded modules

`http_2xx`, `http_post_2xx`, `https_2xx`, `tcp_connect`, `icmp`, `dns_udp`,
`dns_tcp`, `grpc`. Supply your own with `--config /path/to/blackbox.yml` to
override.

## SSH invocation examples

```sh
# single HTTP probe
ssh vm 'bbprobe --module http_2xx --target https://example.com'

# ICMP to an IP
ssh vm 'bbprobe --module icmp --target 10.0.0.1'

# multiple modules, 3 attempts each
ssh vm 'bbprobe --module http_2xx,icmp --target 10.0.0.1 --repeat 3'

# custom config on the VM, longer timeout, debug plaintext included
ssh vm 'bbprobe --config /etc/bbprobe/blackbox.yml --module dns_udp \
        --target 8.8.8.8 --timeout 5s --debug'

# Prometheus text exposition (for scraping/piping)
ssh vm 'bbprobe --module http_2xx --target https://example.com --format prom'
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0`  | All probes/attempts **succeeded**. |
| `1`  | Probes ran but at least one **failed**. |
| `2`  | Usage / config / internal error (message on stderr, **empty stdout**). |

**stdout carries only the JSON/prom payload.** All logging goes to **stderr**.

## JSON schema

```json
{
  "version": "v1.0.0+abc1234",
  "target": "https://example.com",
  "results": [
    {
      "module": "http_2xx",
      "prober": "http",
      "attempt": 1,
      "success": true,
      "duration_seconds": 0.123,
      "metrics": [
        { "name": "probe_success", "value": 1 },
        { "name": "probe_http_status_code", "value": 200 },
        { "name": "probe_http_duration_seconds",
          "labels": { "phase": "connect" }, "value": 0.01 }
      ],
      "debug": "…only present with --debug…"
    }
  ],
  "summary": {
    "probe_success": 1,          // 1 only if EVERY attempt succeeded
    "total": 1,
    "succeeded": 1,
    "failed": 0,
    "latency_seconds": { "min": 0.11, "avg": 0.12, "max": 0.13 }
  }
}
```

- `results[]` has one entry per **module × attempt**.
- `metrics[]` is a faithful flattening of the probe's Prometheus registry
  (name + labels + value), including labeled series such as the
  `probe_http_duration_seconds` phases.
- `summary.probe_success` is the AND across all attempts and matches the exit code.
- `--format prom` instead emits the standard Prometheus text exposition of the
  gathered registry (best used with a single module/attempt).

## ICMP without root

The `icmp` prober needs to send raw ICMP echo packets. **You do not need to run
`bbprobe` as root** — grant one of the following on the VM:

```sh
# Option A: file capability on the binary (per-binary, survives reboots)
sudo setcap cap_net_raw+ep /usr/local/bin/bbprobe

# Option B: allow unprivileged ICMP for a range of GIDs (system-wide)
#   e.g. allow all groups; adjust to your policy
sudo sysctl -w net.ipv4.ping_group_range="0 2147483647"
#   persist:
echo 'net.ipv4.ping_group_range = 0 2147483647' | sudo tee /etc/sysctl.d/99-bbprobe.conf
```

With Option B the embedded `icmp` module uses unprivileged (datagram) ICMP
sockets. Without either, ICMP probes fail with a permission error (exit `1`).

## Robot Framework (SSHLibrary)

```robotframework
*** Settings ***
Library    SSHLibrary
Library    Collections
Library    String

*** Variables ***
${HOST}         vm.example.net
${USER}         tester
${TARGET}       https://example.com
${MAX_LATENCY}  ${2.0}     # seconds

*** Test Cases ***
HTTP Endpoint Is Healthy And Fast
    Open Connection    ${HOST}    prompt=$
    Login              ${USER}    ${EMPTY}    # key-based auth in ~/.ssh
    ${stdout}    ${rc} =    Execute Command
    ...    bbprobe --module http_2xx --target ${TARGET}
    ...    return_stdout=True    return_rc=True
    Close Connection

    Should Be Equal As Integers    ${rc}    0
    ${result} =    Evaluate    json.loads(r'''${stdout}''')    json
    ${success} =    Set Variable    ${result}[summary][probe_success]
    Should Be Equal As Integers    ${success}    1
    ${latency} =    Set Variable    ${result}[summary][latency_seconds][max]
    Should Be True    ${latency} < ${MAX_LATENCY}
    ...    msg=probe latency ${latency}s exceeded ${MAX_LATENCY}s
```

`Execute Command` returns the JSON on stdout and the process exit code via
`return_rc`. Because logs go to stderr, `${stdout}` parses cleanly as JSON.
```
