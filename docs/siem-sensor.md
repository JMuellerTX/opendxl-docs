# SIEM sensor

A DXL fabric is a blind spot for a security operations team: nothing outside the fabric can
say which services are registered right now, which one disappeared at 03:00, which client
certificates are connecting, or who is still negotiating a legacy cipher suite. The fabric
emits most of this — service lifecycle arrives as events on
`/mcafee/event/dxl/svcregistry/register` and `/unregister`, brokers can publish connect and
disconnect events — but nobody consumes it.

The **OpenDXL SIEM sensor** is a small Rust program that subscribes to those events, keeps a
model of the fabric, normalises what it sees to [OCSF](https://schema.ocsf.io/) and CEF, and
forwards it to a SIEM. It is the first OpenDXL component that is useful to someone who is *not*
already running DXL integrations: it makes an existing fabric observable.

!!! note "Status"
    Under development, repository `JMuellerTX/opendxl-siem-sensor` (Apache-2.0, not yet
    published). Everything on this page has been run against the open source broker of the
    [maintained fork](fork.md) (OpenSSL 3 and OpenSSL 4 images). The protocol facts it relies on
    were measured against a Trellix DXL broker 6.1.3 with the Python client; the sensor itself has
    not been run against a Trellix fabric yet.

## How it works

```
        DXL fabric
            │  subscribe: /mcafee/event/dxl/#, configured topics
            │  at start:  svcregistry/query, brokerregistry/query
            ▼
    ┌───────────────────┐
    │  opendxl-siem-    │  parse the DXL envelope (MessagePack)
    │  sensor (Rust)    │  keep service / client / broker state
    │                   │  detect → OCSF Detection Finding
    └────────┬──────────┘
             │
   syslog RFC 5424 (CEF)  ·  HTTP/JSON (OCSF)  ·  Kafka (optional)
             ▼
          SIEM
```

The sensor is a regular DXL client with its own certificate, provisioned like any other
(`provisionconfig`). It sends two requests at start to learn the current services and brokers,
then only listens. It never publishes on business topics.

## What it reports

| DXL source | OCSF class | Notes |
|---|---|---|
| `svcregistry/register` / `unregister` | API Activity (6003), create / delete | Service type, GUID, request channels, TTL, certificate thumbprints of the registering client |
| `clientregistry/connect` / `disconnect` | Network Activity (4001) | Only when the broker publishes them — see below |
| Detections (below) | Detection Finding (2004) | Severity, the client's certificate thumbprint as `suser` |

Detections available today:

| Detection | Signal |
|---|---|
| **Legacy cipher suite** | A client connected with an RSA key-transport suite (`TLS_RSA_*`) — the migration dashboard for the whole [TLS story](broker/tls.md), as a list of thumbprints instead of an assertion |
| **Unknown certificate thumbprint** | A registering service, a connecting client or a publisher whose thumbprint is not on the allow-list (empty list = check off) |
| **Sensitive topic published** | A publisher on a configured topic — topic authorization is open by default, this is the only way to see the gap |
| **Service TTL expired** | A registration ran past its TTL plus the broker's grace period (5 minutes by default) without re-registering or unregistering |
| **Fabric change** | Broker bridge topology changed |
| **Rate anomalies** | Per client and per topic |

The CEF line for a connection carries the transport (`app`), TLS version, cipher suite and
certificate thumbprint as custom strings and the peer address as `src`; a legacy-cipher
detection looks like this on the wire:

```
CEF:0|OpenDXL|RustSensor|1.0|2004|Legacy Cipher Suite|4|msg=Client connected with weak legacy cipher: TLS_RSA_WITH_AES_128_CBC_SHA256 suser=5a752ed6a24f6d2dd77634b0c68dd729b48d4613
```

That line was produced end to end: a Python client forced to TLS 1.2 with `AES128-SHA256`
connected to the fork's broker, the broker reported the suite in its connect event, the sensor
raised the finding.

## Identity: the certificate, not the client ID

Everything the sensor correlates on is the **SHA-1 thumbprint of the client certificate**. That
is not a design choice of the sensor but how the fabric works, measured on the open source broker
and on a Trellix DXL broker 6.1.3 alike: `source_client_id` on every message is the thumbprint,
registry payloads carry it as `clientGuid`, and the configured `ClientId` never appears on the
fabric. See [Who a message is from](concepts/messages.md#who-a-message-is-from). Allow-lists
in the sensor are therefore lists of thumbprints, in the same lowercase-hex form the broker's
`topicauth.policy` uses.

## What the broker has to provide

- **Forward-secrecy cipher suites.** The sensor uses rustls, which does not implement RSA key
  transport at all. It cannot connect to the Docker Hub image from 2021 or to a Trellix DXL
  broker before 6.1.1 — the same situation as every current JDK, Node.js and Python runtime,
  see [TLS and ciphers](broker/tls.md). Brokers from 6.1.1 on, and the fork's images, work.
- **An X.509 v3 client certificate.** rustls rejects v1 certificates. The upstream console
  issued v1 certificates (no extensions at all); the fork's console issues v3 since
  `f4a17e2`, and ePO always has.
- **Connect events, optionally.** No broker publishes `clientregistry/connect` by default —
  neither the open source one nor a Trellix DXL broker 6.1.3 (measured). Without them the sensor
  still sees services and publishers, which is the primary source; with them it also sees every
  connection and can run the cipher detection. The fork's broker publishes them with
  `DXL_SEND_CONNECT_EVENTS=true` and adds TLS version, cipher, thumbprint, address and transport
  to the event — see [Client connect events](broker/index.md#client-connect-events).

## Outputs

- **Syslog / CEF** (RFC 5424 over TCP or UDP) — lands in an ArcSight- or Trellix-style
  collector without a parser.
- **HTTP/JSON** — OCSF documents to a webhook.
- **Kafka** — behind a Cargo feature, because it builds `librdkafka` from source; the sanctioned
  high-volume path off a DXL fabric is the [Databus client](repositories.md#tooling-and-scaffolding),
  and this output speaks to the same brokers.

## Why Rust

The sensor parses untrusted fabric traffic, runs unattended next to a collector, and benefits
from a single static binary with no Python or JDK runtime. rustls sidesteps the OpenSSL
version question this documentation spends two pages on — at the price of not speaking to
RSA-only brokers, which is the right trade for a monitoring tool that exists to retire them.
