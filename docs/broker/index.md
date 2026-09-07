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

## Client connect events

The broker can publish an event for every client that connects or disconnects:
`/mcafee/event/dxl/clientregistry/connect` and `/disconnect`. This is **off by default**
(`sendConnectEvents=false` in `dxlbroker.conf`), and a Trellix DXL broker 6.1.3 does not
publish them either — measured with a subscriber on the topic while a second client
connected. A monitoring tool therefore has to treat these events as an optional source.

Upstream, the payload is `{"clientGuid": "<thumbprint>:<instance guid>"}`. The
[maintained fork](../fork.md) adds what the TLS layer knows at connect time, so the
question "who is still connecting with a legacy cipher suite" can be answered from the
fabric itself:

```json
{
  "clientGuid":     "5a752ed6a24f6d2dd77634b0c68dd729b48d4613:c5c018fe-812e-47a3-856d-9f8a9dfb1426",
  "certThumbprint": "5a752ed6a24f6d2dd77634b0c68dd729b48d4613",
  "tlsVersion":     "TLSv1.3",
  "cipher":         "TLS_AES_256_GCM_SHA384",
  "protocol":       "mqtt",
  "remoteAddress":  "172.17.0.1"
}
```

| Field | Meaning |
|---|---|
| `certThumbprint` | SHA-1 of the client certificate, lowercase hex without colons — the same form `topicauth.policy` uses |
| `tlsVersion` | Negotiated protocol version, `TLSv1.2` or `TLSv1.3` |
| `cipher` | Negotiated cipher suite, **IANA name** (`TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384`), the spelling JSSE, rustls and SIEM products use — not OpenSSL's `ECDHE-RSA-AES256-GCM-SHA384` |
| `protocol` | `mqtt` or `websocket` |
| `remoteAddress` | Peer address as the broker sees it; WebSocket connections report the IPv4-mapped IPv6 form (`::ffff:172.17.0.1`) |

The [SIEM sensor](siem-sensor.md) consumes these fields for its legacy-cipher and
unknown-certificate detections. Every added field is optional and only written when known. The disconnect event still
carries only `clientGuid`, and events from brokers without the change are unchanged, so a
reader that only knows `clientGuid` keeps working. In the fork's container image
`DXL_SEND_CONNECT_EVENTS=true` switches the events on; `docker-compose.test.yml` sets it
for all four TLS profiles. Verified over MQTT and WebSockets against the AlmaLinux image.

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

The [maintained fork](../fork.md) has done this work. Its `master` builds the broker against
**OpenSSL 4.0.2** (compiled from source into `/opt/openssl`, because no distribution packages
4.x yet) and ships two Dockerfiles:

| Dockerfile | Base | Status |
|---|---|---|
| `Dockerfile` (generated from `docker/Dockerfile.template` by `docker/build.sh`) | Debian | Built by the fork's CI on every push |
| `docker/almalinux/Dockerfile` | AlmaLinux 10 builder, `almalinux:10-minimal` runtime | Built and measured 2026-09-07: OpenSSL 4.0.2 as `libssl.so.4`, TLS 1.3 with `X25519MLKEM768`, TLS 1.2 ECDHE, WebSockets on 443 also TLS 1.3, container `healthy` after 10 s, Python 3.12 runtime, no Python 2 |

```bash
git clone https://github.com/derjochenmueller/opendxl-broker
cd opendxl-broker
docker build -f docker/almalinux/Dockerfile -t dxlbroker:almalinux .   # about 25 minutes
docker run -d --name dxlbroker -p 8883:8883 -p 8443:8443 -p 8444:443 dxlbroker:almalinux
```

What the port consisted of, for anyone maintaining a different base:

- OpenSSL 4 makes `ASN1_STRING` opaque and removes the version-locked `TLSv1_2_server_method()`
  family, so the mosquitto-derived core (`src/mqtt-core/`), the certificate-extension parsing in
  `brokerlib` and the pinned libwebsockets fork (`docker/patches/`) all needed changes. The
  same change is what allows TLS 1.3 at all.
- The makefiles ignore `CFLAGS`/`LDFLAGS` and take `ADD_INCLUDE`/`ADD_LIB` instead; the build
  asserts with `ldd` that the binary resolves `libssl.so.4`, because a broker that reports
  OpenSSL 4 while loading the distribution's OpenSSL 3 is worse than a failed build.
- **`WITH_EC`** had to be defined. That was the root cause of the missing forward secrecy:
  elliptic-curve support was compiled out of the core, so no cipher list could enable ECDHE.
- The Python 2 runtime is gone; the console runs on Python 3 from the fixed console fork.
- `DXL_TLS_MODE` selects the cipher profile at start (`modern`, `legacy`, `pfs-only`,
  `trellix-6.1`), see [TLS and ciphers](tls.md); `docker-compose.test.yml` starts all four.

## Related components

- [OpenDXL Console](../repositories.md#tooling-and-scaffolding) — a web UI for browsing the
  fabric, the service registry and live messages.
- [OpenDXL Environment](../repositories.md#containers-and-environments) — a container with a
  broker plus the clients and samples, for workshops and demos.
