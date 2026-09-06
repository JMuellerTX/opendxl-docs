# Architecture

This page describes what a DXL fabric is made of and how a message travels through it. It is
the conceptual model; the concrete API calls are in the [client](clients/python.md) pages.

## The pieces

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             DXL fabric                                   │
│                                                                          │
│    ┌──────────┐      bridge      ┌──────────┐      bridge   ┌─────────┐  │
│    │ broker A │◄────────────────►│ broker B │◄─────────────►│ broker C│  │
│    └────┬─────┘                  └────┬─────┘               └────┬────┘  │
└─────────┼─────────────────────────────┼──────────────────────────┼───────┘
     TLS  │  MQTT 8883 / WSS 443        │                          │
   ┌──────┴──────┐              ┌───────┴───────┐          ┌───────┴──────┐
   │   client    │              │    service    │          │   client     │
   │ (publisher) │              │ (registered   │          │ (subscriber) │
   │             │              │  request      │          │              │
   │             │              │  handler)     │          │              │
   └─────────────┘              └───────────────┘          └──────────────┘
```

**Broker.** An MQTT broker with DXL semantics on top: it authenticates clients by certificate,
enforces topic authorization, keeps a registry of which service is reachable where, and
bridges to other brokers so that a fabric can span sites. The open source broker is a
mosquitto derivative; a Trellix DXL broker is the commercial equivalent and speaks the same
protocol. Default ports: **8883** (MQTT over TLS), **443/8443** (WebSockets over TLS).

**Client.** Any process holding a certificate signed by the fabric's CA. A client can publish
events, subscribe to events, send requests, and register services. There is no separate
"producer" and "consumer" role — the distinction is what a given process chooses to do.

**Service.** A client that has registered one or more *request topics* with the fabric. The
broker then routes requests on those topics to it and relays the response back to the caller.
Registration is a message like any other, sent to
`/mcafee/service/dxl/svcregistry/register`, and it carries a **time-to-live**: a service that
stops renewing its registration disappears from the fabric on its own.

## Message types

The wire format is [MessagePack](https://msgpack.org/) — a compact binary encoding, not JSON.
Every message carries a version, a message ID, the source client and broker IDs, optional
destination broker/client filters, and an opaque `payload` of bytes. What the payload contains
is up to the service contract; the reference integrations use UTF-8 JSON.

| Type | Constant | Semantics |
|---|---|---|
| **Event** | `MESSAGE_TYPE_EVENT` (2) | Fire-and-forget publish to a topic. Every subscriber receives a copy. No reply, no delivery guarantee beyond MQTT QoS. |
| **Request** | `MESSAGE_TYPE_REQUEST` (0) | Addressed to a *service* topic. Exactly one registered instance handles it. The caller blocks (or gets a callback) until a response arrives or the timeout expires. |
| **Response** | `MESSAGE_TYPE_RESPONSE` (1) | The service's answer, correlated to the request by its message ID. |
| **Error** | `MESSAGE_TYPE_ERROR` (3) | A response subtype carrying an error code and message instead of a result. |

The two interaction styles map onto different problems and it is worth being deliberate
about which one an integration uses:

- **Events** for "this happened" — a file was convicted, a host changed posture, an IOC was
  observed. Adding a consumer later costs nothing and the publisher never learns about it.
- **Requests** for "tell me / do this" — reputation of this hash, run this query, set this
  tag. There is exactly one answer and the caller waits for it.

An integration that publishes an event *and* expects someone to act on it within a deadline
is usually a request wearing the wrong hat.

## Topics and authorization

Topics are slash-separated strings, conventionally namespaced by vendor and product
(`/mcafee/service/tie/file/reputation`, `/mcafee/event/…`). The broker enforces, per
certificate, which topics a client may publish to and subscribe from — so authorization is a
fabric-level policy, not something each service re-implements. This is covered in
[Topics and authorization](concepts/topics-and-authorization.md).

Certificates are the identity. There is no username/password path for the fabric itself; a
client is provisioned once (see [Getting started](getting-started.md)), receives a certificate
signed by the fabric CA, and that certificate's identity is what topic policy is written
against.

## What travels where — a request in full

1. The caller creates a `Request` for topic `T`, sets a payload, and calls `sync_request`.
2. The client library publishes it on `T` and starts a timeout (default 2 minutes).
3. The broker looks up the service registry for `T`, picks one registered instance, and
   forwards the message to the broker that instance is connected to.
4. The service's request callback runs, builds a `Response` (or an `ErrorResponse`), and sends
   it back on the reply topic embedded in the request.
5. The caller's client library correlates the response to the pending request by message ID
   and returns it to the caller — or raises a timeout error if nothing arrived.

Two operational consequences follow from step 3. Requests are load-balanced across service
instances, so a service must be idempotent or partition its work itself; and if no instance is
registered, the caller gets an error response, not silence.

## Connection behaviour

Client connections are long-lived and self-healing. The defaults in the Python client are:

| Setting | Default | Meaning |
|---|---|---|
| `connect_retries` | `-1` | Retry forever when the initial connect fails |
| `reconnect_when_disconnected` | `true` | Reconnect after a dropped connection |
| `reconnect_delay` / `_max` | 1 s / 60 s | Backoff window |
| `reconnect_back_off_multiplier` | 2 | Exponential growth of the delay |
| `keep_alive_interval` | 1800 s | MQTT keep-alive |

`connect_retries = -1` is worth knowing about: a misconfigured client does not fail fast, it
retries indefinitely. Applications that need a startup deadline should set a finite value.
See [Compatibility](compatibility.md) for the TLS settings that decide whether the connection
can be established at all.

## Deployment topologies

- **Single broker.** A container on a laptop, or one broker for a lab. Everything in
  [Getting started](getting-started.md) uses this.
- **Broker mesh.** Several brokers bridged together; clients connect to whichever broker is
  nearest and the fabric routes across bridges. The client configuration lists several
  brokers and the client measures which one to prefer.
- **Managed fabric.** A Trellix DXL deployment where brokers are managed by ePolicy
  Orchestrator, which also acts as the certificate authority for client provisioning. OpenDXL
  clients are first-class participants; see [Compatibility](compatibility.md).
