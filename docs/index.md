# OpenDXL

OpenDXL is the open source side of the **Data Exchange Layer (DXL)** — a publish/subscribe
and request/response messaging fabric built for security tooling. Instead of wiring every
product to every other product point-to-point, each participant connects once to the fabric
and then publishes events, consumes events, or exposes a service that others can call.

The fabric itself is an MQTT-based broker mesh. What OpenDXL adds on top is a message model
(events, requests, responses, errors), a certificate-based identity and authorization model,
and a set of client libraries and reference integrations released under the
Apache License 2.0.

## Why a fabric instead of point-to-point integrations

A security estate with *n* products that all need to talk to each other needs on the order of
*n²* integrations, each with its own credentials, retry logic, data format and lifecycle. On a
fabric, each product implements one connection and one message contract:

```
Point-to-point                       DXL fabric

  EDR ── SIEM                          EDR ─┐
   │  ╳   │                            SIEM ─┤
  TIP ── SOAR                          TIP ─┼── [ broker mesh ] ── consumers
   ╲     ╱                             SOAR ─┘
    Sandbox                          Sandbox ─┘

  n·(n-1)/2 integrations             n connections, shared contracts
```

The practical consequences are the ones that matter operationally: a new consumer of threat
data is a subscription, not a project; a reputation lookup that used to be a REST integration
becomes a request to a topic; and a product that goes away stops publishing without breaking
anyone who was not depending on it directly.

## What is in the OpenDXL ecosystem

| Layer | What it is | Where |
|---|---|---|
| **Broker** | Open source DXL broker (MQTT + WebSockets, TLS, topic authorization), distributed as a Docker image | [The broker](broker/index.md) |
| **Clients** | Libraries that connect to the fabric and send/receive DXL messages — Python, Java, JavaScript/Node.js, Node-RED | [Clients](clients/python.md) |
| **Services** | Long-running processes that register a topic and answer requests — the reference ones wrap third-party APIs | [Integrations](integrations.md) |
| **Client libraries for services** | Typed wrappers so callers do not hand-build request payloads (TIE, ePO, MAR, VirusTotal, MISP, …) | [Repositories](repositories.md) |
| **Bootstrap** | Code generator that scaffolds a new DXL service or client project | [Repositories](repositories.md#tooling-and-scaffolding) |

## Where to start

- **Never used DXL before** → [Architecture](architecture.md) explains brokers, clients,
  services and the message types, then [Getting started](getting-started.md) gets a broker and
  a first message running locally in about ten minutes.
- **Writing an integration** → pick a client ([Python](clients/python.md),
  [Java](clients/java.md), [JavaScript](clients/javascript.md),
  [Node-RED](clients/node-red.md)) and read [Services and requests](concepts/services.md).
- **Operating a fabric** → [The broker](broker/index.md) and [TLS and ciphers](broker/tls.md).
- **Planning against a Trellix DXL deployment** → [Compatibility](compatibility.md) has the
  version, TLS and cipher matrix for DXL 6.1.x and ePO 5.10 SP1.

## Project status

OpenDXL was started at McAfee in 2016 and released under the Apache License 2.0. McAfee
Enterprise and FireEye combined into **Trellix** in 2022; the legal entity behind the
brand today is **Musarubra US LLC**. Upstream commit activity on most OpenDXL repositories
stopped between 2019 and 2021, which means the published packages predate Python 3.10, the
current Node.js LTS lines, and the TLS policy of current JDKs.

The code is still Apache-2.0 and still useful — the fabric protocol has not changed — but
anyone adopting it today should read [Compatibility](compatibility.md) before pinning the
released artifacts. All 45 repositories are forked and kept working by
[@JMuellerTX](https://github.com/JMuellerTX); [the maintained fork](fork.md) lists every fix
and how to install it. [Project history and stewardship](history.md) covers what changed,
what that means for support expectations, and where discussion happens now
([community](community.md)).
