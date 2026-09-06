# Compatibility

What works with what, and which of the published artifacts you should not use as they are.
This page is the one to read before starting an integration, not after.

## The short version

The DXL **protocol** has not changed and is not the problem. The published **packages** are —
they were last released between 2019 and 2021 and predate Python 3.10, current JDK security
policy, current Node.js LTS lines, and MessagePack 1.0. Three specific breakages account for
almost everything you will hit:

1. **TLS.** Old brokers offer only RSA key-transport suites; current runtimes no longer
   enable those.
   → [TLS and ciphers](broker/tls.md)
2. **MessagePack.** The published Python client pins `msgpack<1.0.0`, which is a 2019 release
   with a known advisory and does not install cleanly next to anything current.
3. **`pkg_resources`.** `dxlbootstrap` 0.2.2 imports it; setuptools ≥ 82 no longer ships it,
   so every Python service built on the bootstrap fails at import.

## Runtime support

| Client | Published release | Declares | Actually works on |
|---|---|---|---|
| Python (`dxlclient`) | 5.6.0.4 (2020) | `python_requires>=2.7.9` | 3.8–3.9 as released; 3.10+ needs the TLS and msgpack fixes |
| Java (`com.opendxl:dxlclient`) | 0.2.6 (2020) | Java 8 | Java 8–21; **11+ needs the `TLS_RSA_*` workaround** — see [Java client](clients/java.md#tls-on-current-jdks) |
| JavaScript (`@opendxl/dxl-client`) | 0.1.4 (2020) | Node 8+ | Runs on current Node, but its `mqtt` 2.x tree carries advisories |
| Node-RED nodes | 0.1.x (2020) | Node-RED 0.19+ | Works on Node-RED 4.x; inherits the JavaScript client's dependency tree |

## Broker and fabric versions

| Fabric | TLS | Ciphers | Notes |
|---|---|---|---|
| OpenDXL broker (Docker image, 2021) | 1.2 max | 8 suites, all `TLS_RSA_*`, no forward secrecy | OpenSSL 1.0.2 on Debian stretch (EOL 2022). `WITH_EC` not compiled in — see [The broker](broker/index.md#building-a-current-image) |
| Trellix DXL < 6.1.1 | 1.2 max | RSA key transport only | Same handshake problem as above |
| Trellix DXL 6.1.1+ | 1.2 max | 4 ECDHE (secp256r1) + 8 RSA key transport | Measured against a 6.1.3.55 broker. ECDHE available; the first version a stock modern client connects to unaided |
| Trellix DXL 6.1.2+ | 1.2 max | as above | Adds IPv6 broker listeners |
| OpenDXL broker, fork on OpenSSL 4 | **1.3** | 3 TLS 1.3 suites + 15 on TLS 1.2 | Measured. TLS 1.3 key exchange is **X25519MLKEM768**, a post-quantum hybrid. See [the maintained fork](fork.md) |
| ePO 5.10 SP1 U7 (management service) | **1.3** | 4 TLS 1.3 suites + 4 ECDHE on 1.2 | Measured. `provisionconfig`/`updateconfig` talk to this, not to the MQTT listener. **Offering TLS 1.3 depends on the web server configuration** — the same server presented TLS 1.2 only until Apache was restarted |

The broker appliance in DXL 6.1.x still runs OpenSSL 1.0.2zk, so **TLS 1.3 is not available on
the fabric connection** regardless of client support — confirmed by scanning a 6.1.3.55 broker.
Against a Trellix fabric, TLS 1.2 with forward secrecy remains the realistic target.

The open source broker is no longer bound by that. Built against OpenSSL 4.0.2, it negotiates
TLS 1.3 with an `X25519MLKEM768` key exchange — hybrid X25519 plus ML-KEM-768, so the session
key survives an attacker who records it now and has a quantum computer later. That makes the
fork's broker the only DXL broker offering TLS 1.3 at all, which matters mainly as somewhere
to test a client's TLS 1.3 path before the commercial line gets there.

!!! tip "Scan the endpoint, do not infer from the version"
    A version number tells you what is *possible*; only a scan tells you what is *offered*.
    Both directions of that were observed on one lab fabric in a single session: the open
    source broker offers more suites than its reputation suggests (eight, not one), and an
    ePO whose version implies TLS 1.3 presented TLS 1.2 only until its web server was
    restarted. Use `nmap -Pn -sT --script ssl-enum-ciphers -p <port> <host>`.

FIPS 140-3 on ePO 5.10 SP1 U7 removes RSA key-transport suites and SHA-1 outright. A fabric
on that profile will not accept a client configured for `AES128-SHA256` — which makes the
forward-secrecy-only cipher default the correct one going forward, not merely the tidier one.

## Fixes available in the maintained fork

All 45 repositories are forked and maintained by
[**@JMuellerTX**](https://github.com/JMuellerTX) — 160 commits across 43 of them, including
16 security changes and 35 bug fixes. [The maintained fork](fork.md) lists every one of them
per repository, and explains how to consume them.

None of it is released to PyPI, npm, Docker Hub or Maven Central, so consuming a fix means
installing from git. The summary below covers the fixes that change what works; the full
inventory is on the fork page.

### Python client

| Area | Change |
|---|---|
| MessagePack | Wire-format compatibility with msgpack ≥ 1.0; the `msgpack<1.0.0` pin removed; payloads > 1 MiB handled |
| Threading | Thread leak after a failed `connect()`; reconnect deadlock; service TTL timer; async callback leak |
| `connect()` | No longer waits the full callback timeout after the connect has already failed — a failing connect took roughly twice as long as it needed to |
| TLS | `PROTOCOL_TLS_CLIENT`; `TlsCiphers` config key; `TlsMinVersion` (default 1.2); `VerifyHostname` (default off) |
| CLI | `--key-type` / `--key-bits` / `--key-curve` for FIPS-profile CSRs |
| IPv6 | Broker address parsing for `[::1]` and `id;port;host;2001:db8::1` |
| Python | 3.9–3.14 CI matrix, pytest suite instead of nose |

The client is maintained on two lines, because the right cipher default depends on the fabric:

- **`master`** — forward-secrecy suites only. For ePO 5.10 SP1 U7+ / DXL 6.1.1+.
- **`epo-legacy`** — forward secrecy first, `AES128-SHA256` as fallback. For older fabrics and
  the open source broker.

### Java client

`TlsCompatibility` re-enables `TLS_RSA_*` before JSSE initializes; jackson-databind
2.9.7 → 2.22; msgpack 0.6.7 → msgpack-core 0.9.12 with wire-format reference vectors;
log4j, BouncyCastle, httpclient and JUnit updated; one branch per JDK line (21/17/11/8).

### JavaScript

`mqtt` 2.14 → 5.15 (which is what clears the `ws` advisories), `tmp` 0.2.x, `uuid` 11,
`request` replaced. **The downstream packages do not benefit until a release reaches npm**,
because they depend on the published `@opendxl/dxl-client@0.1.4`.

### Product client libraries

Three of these carried real defects, not just stale packaging:

- **pxGrid** — an event callback raised whenever `content` was not base64-encoded JSON, which
  killed the callback thread instead of skipping the message.
- **MAR** — `TypeError` when the service returned a non-string error body, so a failed search
  surfaced as a crash rather than an error.
- **Elasticsearch** — `AttributeError` on error responses that carry no `info` field, plus a
  `urllib3<1.25` pin that dragged in nine known vulnerabilities.

Plus `stix2 < 3` for OpenC2 (openc2 1.0.5 is incompatible with stix2 3.x) and an ePO client
`SyntaxWarning` from an `is` comparison on an integer.

### Services and bootstrap

`dxlbootstrap` fixed for setuptools ≥ 82 (the `pkg_resources` import that broke every service
at import time); Python 3.12+ compatibility across all eight reference services;
Elasticsearch pinned to a supported range instead of `urllib3<1.25`; DomainTools API 2.x;
`enum34` dropped from MISP; all eight build on `python:3.13-slim`.

One security fix worth naming: the **MaxMind service downloaded its database over plain
HTTP**. It now uses HTTPS.

### Broker and console

The root cause of the missing forward secrecy was `WITH_EC` never being defined at build
time, so ECDHE was compiled out regardless of the `ciphers=` setting. The fork rebuilds on Debian 12 /
UBI 9 against OpenSSL 3 (FIPS via the provider API), offers ECDHE/DHE, and exposes
`DXL_TLS_MODE=modern|legacy|pfs-only|trellix-6.1` — see [TLS and ciphers](broker/tls.md). The bundled
console had Python 3 defects that broke provisioning outright; it now runs on 3.8–3.14.

### Node-RED and containers

Node-RED 4.x for the test suites, and the `@opendxl/dxl-client ^0.0.1` ranges corrected to
`^0.1.0` — the old range installed two copies of the client side by side. The environment and
node-red-docker images move to maintained bases.

## Open items

Things that are known, not yet resolved, and worth knowing about before you depend on them.

| Item | Impact |
|---|---|
| **CLI truststore default** | `provisionconfig` without `-e/--truststore` does not verify the management service's certificate — it only suppresses the warning. Pass the CA bundle explicitly on a managed fabric. |
| **Dual-stack connect** | The client's per-address probe has a 1-second timeout and no parallel attempt (no Happy Eyeballs). A broker with an unroutable AAAA record can make connects slow. |
| **pxGrid 2.0** | DXL 6.1.0+ ships a pxGrid 2.0 connector. `opendxl-pxgrid-client-python` has not been verified against 2.0 topic and payload formats. |
| **PyPI / npm / Maven releases** | Until the fixed client is published, every downstream project keeps the old transitive dependencies regardless of its own fixes. |
| **Databus JAR** | Removed from the DXL 6.1.0 broker bundle; `opendxl-databus-client-java` must now be versioned independently. |

## Choosing versions for a new integration

1. **Find out what the fabric offers** — `openssl s_client -connect broker:8883` settles the
   cipher question in one command.
2. **Pick the client line** from that: forward-secrecy-only if the fabric is DXL 6.1.1+ or
   ePO U7+, the fallback line otherwise.
3. **Do not pin the published PyPI/npm artifacts for anything new.** Install the client from
   git until releases exist, and treat the dependency advisories as your problem rather than
   the packaging system's.
4. **Set a finite `connect_retries`** so a misconfiguration fails visibly instead of retrying
   forever.
