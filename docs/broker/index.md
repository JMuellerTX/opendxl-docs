# The broker

The OpenDXL broker is the open source implementation of a DXL broker: an MQTT broker derived
from mosquitto, with DXL semantics layered on top — certificate-based client identity, topic
authorization, a service registry, and bridging to other brokers.

- Upstream: [opendxl/opendxl-broker](https://github.com/opendxl/opendxl-broker)
- Image: [`opendxl/opendxl-broker`](https://hub.docker.com/r/opendxl/opendxl-broker) on Docker Hub

It speaks the same protocol as a Trellix DXL broker. A client provisioned against one works
against the other; what differs is management (files here, ePolicy Orchestrator there),
clustering, and the TLS profile.

## Running one

```bash
docker run -d --name dxlbroker \
  -p 8883:8883 -p 8443:8443 -p 8444:443 \
  opendxl/opendxl-broker
```

| Port | Purpose |
|---|---|
| 8883 | MQTT over TLS — the client connection |
| 8443 | Management service — certificate signing, used by `provisionconfig` |
| 443 | WebSockets over TLS (mapped above to host port 8444) |

On first start the container creates its own certificate authority, so a fresh container is
immediately able to sign client certificates. Persist `/dxlbroker-volume` if you want the CA
and the broker identity to survive a container replacement — without it, every restart from a
fresh image invalidates every certificate it previously issued.

## Configuration

| File | Purpose |
|---|---|
| `dxlbroker.conf` | Ports, message size limit, logging, cipher list |
| `topicauth.policy` | Per-topic send/receive allow-lists by certificate thumbprint |
| `general.policy` | Keep-alive for broker bridges, connection limit |
| `brokerstate.policy` | Broker mesh state |

Selected defaults:

| Setting | Default | Notes |
|---|---|---|
| `listenPort` | 8883 | MQTT/TLS |
| `messageSizeLimit` | `1048576` (1 MiB) | Larger messages are rejected, not truncated |
| `maxLogSize` / `maxLogFiles` | 1 MiB / 10 | Rotating broker log |
| `logLevel` | `info` | `error`, `warn`, `info`, `debug` |
| `connectionLimit` | `0` | Unlimited client connections |
| `keepAlive` | 1 min | Between bridged brokers |

Topic authorization is covered in
[Topics and authorization](../concepts/topics-and-authorization.md); the cipher list is the
subject of [TLS and ciphers](tls.md) and is the setting most likely to need attention.

## The container image is old

The image published on Docker Hub was built in 2021 from `debian:stretch-slim` — an operating
system that reached end of life in June 2022 — with OpenSSL 1.0.2 and a Python 2 runtime for
the bundled console. Consequences a new user runs into within the first hour:

- **No forward secrecy at all.** The image offers eight TLS 1.2 suites and every one of them
  is RSA key transport (`TLS_RSA_*`). Recent Python, JDK and Node.js versions dropped that
  whole class from their defaults, so a stock modern client fails the handshake. See
  [TLS and ciphers](tls.md).
- **No TLS 1.3.** OpenSSL 1.0.2 predates it. TLS 1.2 is the ceiling.
- **Unpatched base.** The OS packages carry four years of unfixed advisories.

This is a lab and test broker. It was never positioned as a production broker, and its current
state makes that clearer than it used to be.

## Building a current image

The Dockerfile is generated from `docker/Dockerfile.template` by `docker/build.sh`; a Red Hat
UBI variant lives in `docker/redhat-ubi`. Rebuilding on a maintained base with OpenSSL 3 is
the practical way to get a broker that a current client can talk to. The known work involved:

- Base image to Debian 12 or UBI 9, `libssl-dev`/`libssl3` instead of `libssl1.0-dev`.
- Fix the OpenSSL 1.0 API calls in the mosquitto-derived core (`src/mqtt-core/`) for OpenSSL 3.
- **Define `WITH_EC`.** This is the root cause of the missing forward secrecy: elliptic-curve
  support is compiled out of the broker core, so ECDHE suites cannot be negotiated no matter
  what the cipher list says. Everything else about the cipher configuration is downstream of
  this one build flag.
- Drop the Python 2 runtime — it exists only for the bundled console, which a test broker
  does not need.

## Related components

- [OpenDXL Console](../repositories.md#tooling-and-scaffolding) — a web UI for browsing the
  fabric, the service registry and live messages.
- [OpenDXL Environment](../repositories.md#containers-and-environments) — a container with a
  broker plus the clients and samples, for workshops and demos.
