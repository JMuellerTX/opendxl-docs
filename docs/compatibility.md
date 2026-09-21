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
| Python (`dxlclient`) | 5.7.0.1 (2025-01-30) | `python_requires>=2.7.9` | 3.8–3.9 as released; 3.10+ needs the TLS and msgpack fixes. The 2025 release changed the copyright headers, not the code that matters here: it still pins `msgpack<1.0.0`, still calls `ssl.PROTOCOL_SSLv23` with `tls_insecure_set(True)`, and still vendors `oscrypto` |
| Java (`com.opendxl:dxlclient`) | 0.2.6 (2020-12-01) | Java 8 | Java 8–21; **11+ needs the `TLS_RSA_*` workaround** — see [Java client](clients/java.md#tls-on-current-jdks) |
| JavaScript (`@opendxl/dxl-client`) | 0.1.4 (2024-09-17) | Node 8+ | Runs on current Node, but its `mqtt` 2.x tree carries advisories |
| Node-RED nodes | 0.1.x (2020) | Node-RED 0.19+ | Works on Node-RED 4.x; inherits the JavaScript client's dependency tree |

## Broker and fabric versions

!!! info "Where the measured numbers come from"
    Every "measured" below is a scan of a lab installation — ePolicy Orchestrator 5.10
    SP1 U7 with a DXL 6.1.3.55 broker on a local VM, and the container images for the
    open source side. No production or customer system was involved, and nothing here
    needs one: `openssl s_client` and `nmap ssl-enum-ciphers` against your own fabric
    reproduce all of it in a minute.

| Fabric | TLS | Ciphers | Notes |
|---|---|---|---|
| OpenDXL broker (Docker image, 2021) | 1.2 max | 8 suites, all `TLS_RSA_*`, no forward secrecy | OpenSSL 1.0.2 on Debian stretch (EOL 2022). `WITH_EC` not compiled in — see [The broker](broker/index.md#building-a-current-image) |
| Trellix DXL < 6.1.1 | 1.2 max | RSA key transport only | Same handshake problem as above |
| Trellix DXL 6.1.1+ | 1.2 max | 4 ECDHE (secp256r1) + 8 RSA key transport | Measured against a 6.1.3.55 broker. ECDHE available; the first version a stock modern client connects to unaided |
| Trellix DXL 6.1.2+ | 1.2 max | as above | Adds IPv6 broker listeners |
| OpenDXL broker, fork on OpenSSL 4 | **1.3** | 3 TLS 1.3 suites + 15 on TLS 1.2 | Measured. TLS 1.3 key exchange is **X25519MLKEM768**, a post-quantum hybrid. See [the maintained fork](fork.md) |
| ePO 5.10 SP1 U7 (management service) | **1.3** | 4 TLS 1.3 suites + 4 ECDHE on 1.2 | Measured. `provisionconfig`/`updateconfig` talk to this, not to the MQTT listener. **Offering TLS 1.3 depends on the web server configuration** — the same lab server presented TLS 1.2 only until Apache was restarted |

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
[**@JMuellerTX**](https://github.com/JMuellerTX) — 330 commits across 44 of them, including
51 security changes and 59 bug fixes. [The maintained fork](fork.md) lists every one of them
per repository, and explains how to consume them.

### Tags, branches and what a reference should point at

The fork uses three kinds of git reference, and the difference is deliberate:

| Reference | Where | Why |
|---|---|---|
| `fork-2026-09-21` | Dockerfiles | A **collective tag**, one in each of the 44 repositories the fork changed (`opendxl-build-status` has none, because it has no fork commit), marking the state at the end of a connected run of sessions. An image has to be reproducible. |
| `fork-2026-09-21-epo-legacy` | Dockerfiles that need the fallback line | The `epo-legacy` branch of the Python client keeps `AES128-SHA256` for brokers older than DXL 6.1.1; `master` is forward secrecy only. One tag for both lines would have moved every image to the other one. |
| `@master` / `@epo-legacy` | `setup.py`, CI workflows | A branch says which **line** a library needs, not which build shipped. CI tests the tip on purpose. |

These are not the `v<version>+fork.n` tags. Those mark a **release** that carries
artifacts; the collective tag is a reproducibility anchor and carries nothing.

`@master` in an image was never reproducible, and it is not even reliably current:
Docker caches the layer as long as the line does not change, so a rebuild after a fix
can still contain the build before it.

### Installing from a clone

`setup.py` in the Python repositories keeps naming `dxlclient` and `dxlbootstrap` by
plain name, so **a bare `pip install .` resolves them from PyPI** - and the published
`dxlclient` requires `msgpack<1.0.0` while the published `dxlbootstrap` imports
`pkg_resources`, which setuptools 82 removed. Install the fork's builds first:

```bash
pip install "dxlclient @ git+https://github.com/JMuellerTX/opendxl-client-python@epo-legacy"
pip install "dxlbootstrap @ git+https://github.com/JMuellerTX/opendxl-bootstrap-python@master"
pip install .
```

That is what every CI here does, and what the Dockerfiles do in one resolver pass, so
neither ever reaches PyPI for these two.

??? note "Why not a direct reference in `setup.py`, which would make this automatic"

    It was tried on 2026-09-21 and reverted the same day. A PEP 508 direct reference
    does remove the PyPI resolution - measured, `msgpack 1.2.2` instead of `0.6.2` - but
    it lands in the wheel metadata, and that costs more than it buys:

    * **Images stop building.** Where a Dockerfile resolves the pinned `ARG` URL and `.`
      in one pass, pip sees two different direct URLs for one project name and fails with
      `ResolutionImpossible`, even when the versions are identical.
    * **Offline installs stop working.** The broker and console runtime stages install
      from pre-built wheels with `--no-index`; a direct URL in the metadata needs `git`
      and GitHub at install time. An air-gapped or mirrored install - realistic for ePO -
      fails where a version specifier resolved locally.
    * **The `master` line becomes uninstallable.** `dxlbootstrap` would hard-require the
      `epo-legacy` client, so the forward-secrecy-only line could no longer be deployed
      through these packages at all.
    * **The pin becomes nominal.** A `pip install .` after the pinned `ARG` re-resolves
      the branch, so the image no longer matches its own pin.

    The only case a direct reference improves is someone cloning and running
    `pip install .` without reading anything. That is worth documenting, not worth those
    four costs. The real fix is one release from upstream - see below.

### What a clean master and clean registries would take

Everything below is blocked on someone who is not the fork. Listing it precisely is the
point: each line names the one party who can act, and what it unlocks.

| What | Who can do it | Why only them | What it unlocks |
|---|---|---|---|
| **A clean upstream `master`** | the OpenDXL maintainers | Only they can merge into `opendxl/*`. The fork is 330 commits across 44 repositories, on branches with clean history, and every repository still records `opendxl/<name>` as its parent - so a pull request arrives the ordinary way. | The fixes stop being a fork. Downstream projects get them without changing a single reference. |
| **PyPI `dxlclient`** | the account that owns the name | A PyPI name belongs to an **account**, not to a domain. No DNS record, no trademark and no fork can obtain it; `opendxl.com` is irrelevant here. | One upload without the `msgpack<1.0.0` pin ends the transitive advisory in **20 downstream projects** at once. Nothing else on this page comes close in value per effort. |
| **Maven Central `com.opendxl`** | whoever holds `opendxl.com` **and** the Central account | Central verifies a namespace by a **DNS TXT record on the matching domain**. This one really is domain-bound - the opposite of PyPI, and the two are regularly confused. | Java consumers get the fixed client under the coordinates their builds already resolve. |
| **npm `@opendxl`** | an owner of the npm organisation | A scope is an npm organisation; membership is the only key. | Same for the JavaScript line, including the `tmp`/`uuid` chain the fork works around with overrides. |

What the fork can do without any of them, and has: publish to **GitHub Releases, GitHub
Packages and GHCR** under a `fork.n` version marker, and pin its own images to a
collective tag. What it deliberately will not do is occupy any of those three
namespaces - a fork publishing under a name it does not own is indistinguishable from
the supply-chain attack described in
[Security](security.md#package-names-are-a-security-boundary).

**The order that matters:** the upstream release is worth more than everything else
combined, it needs no domain, no legal step and no coordination with the fork - and it
is the one thing the fork cannot substitute for.

None of it is on PyPI, npm, Docker Hub or Maven Central - those namespaces belong to the
upstream project (see [Security](security.md#package-names-are-a-security-boundary)). The fork
publishes its own releases instead: a wheel, the Java jars, an npm tarball and a broker image
on GHCR, each keeping the upstream name and carrying a `fork.n` version marker. [The
maintained fork](fork.md#using-the-fork) has the commands. The summary below covers the fixes
that change what works; the full inventory is on the fork page.

### Python client

| Area | Change |
|---|---|
| MessagePack | Wire-format compatibility with msgpack ≥ 1.0; the `msgpack<1.0.0` pin removed; payloads > 1 MiB handled |
| Threading | Thread leak after a failed `connect()`; reconnect deadlock; service TTL timer; async callback leak |
| `connect()` | No longer waits the full callback timeout after the connect has already failed — a failing connect took roughly twice as long as it needed to |
| TLS | `PROTOCOL_TLS_CLIENT`; `TlsCiphers` config key; `TlsMinVersion` (default 1.2); `VerifyHostname` (default off) |
| CLI | `--key-type` / `--key-bits` / `--key-curve` for FIPS-profile CSRs; the management server's certificate is validated by default; `cryptography` replaces the unmaintained `oscrypto` submodule and `asn1crypto` |
| IPv6 | Broker address parsing for `[::1]` and `id;port;host;2001:db8::1` |
| Python | 3.9–3.14 CI matrix, pytest suite instead of nose |

The client is maintained on two lines, because the right cipher default depends on the fabric:

- **`master`** — forward-secrecy suites only. For ePO 5.10 SP1 U7+ / DXL 6.1.1+.
- **`epo-legacy`** — forward secrecy first, `AES128-SHA256` as fallback. For older fabrics and
  the open source broker.

### Java client

`TlsCompatibility` re-enables `TLS_RSA_*` before JSSE initializes; TLS 1.3 is reachable and
`TlsMinVersion`, `VerifyHostname` and `TlsCiphers` (JSSE suite names, not an OpenSSL cipher
list) match the Python client's config keys; the provisioning CLI validates the management
server's certificate and `-e/--truststore` works at all; jackson-databind 2.9.7 → 2.22;
msgpack 0.6.7 → msgpack-core 0.9.12 with wire-format reference vectors; log4j, BouncyCastle,
httpclient and JUnit updated; one branch per JDK line (21/17/11/8).

### JavaScript

`mqtt` 2.14 → 5.15 (which is what clears the `ws` advisories), `tmp` 0.2.x, `uuid` 11,
`request` replaced. The downstream packages (`node-red-contrib-dxl-*`, the ePO/TIE/MAR client
libraries) depend on the published `@opendxl/dxl-client@0.1.4`, so they keep the old tree
until something replaces it. The fork's release tarball does exactly that: it keeps the
`@opendxl/dxl-client` name and versions itself `0.1.4+fork.1`, and semver ignores build
metadata when matching ranges, so `npm install <tarball url>` satisfies their `^0.1.x` without
editing a single downstream `package.json`.

!!! note "Published versions, checked against the registries on 2026-09-07"

    PyPI has moved since 2020, npm has too, and neither carries the fixes: `dxlclient`
    5.6.0.5 (2024-07-17), 5.7.0.0 and **5.7.0.1** (both 2025-01-30) are the releases after
    5.6.0.4, and `@opendxl/dxl-client` **0.1.4** was published on 2024-09-17 (0.1.3 a month
    earlier). Maven Central is the exception: `com.opendxl:dxlclient` **0.2.6** is still the
    2020-12-01 build. What changed in the newer releases is packaging and copyright headers -
    the msgpack pin, the TLS context and the vendored `oscrypto` are unchanged, so everything
    on this page still applies to the current releases.

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
`DXL_TLS_MODE=modern|legacy|pfs-only|trellix-6.1` — see [TLS and ciphers](broker/tls.md), where the
profile now also fixes the protocol ceiling, because a cipher list reaches TLS 1.2 and below and
the 1.3 suites are a separate list. The bundled console had Python 3 defects that broke
provisioning outright; it now runs on 3.8–3.14 — and has no hardcoded password any more, see
[Security guidance](security.md#the-one-password-the-management-console).

### Node-RED and containers

Node-RED 4.x for the test suites, and the `@opendxl/dxl-client ^0.0.1` ranges corrected to
`^0.1.0` — the old range installed two copies of the client side by side. The environment and
node-red-docker images move to maintained bases.

## Open items

Things that are known, not yet resolved, and worth knowing about before you depend on them.

| Item | Impact |
|---|---|
| **CLI truststore default** | Resolved in the fork: `provisionconfig`/`updateconfig` now validate the management service's certificate against the system's trusted CAs by default; `-e/--truststore` names a private CA (the ePO server CA), `--insecure` disables validation explicitly. Measured against a lab ePO 5.10 on Python 3.14: without `-e` the command fails with a message that points to `-e`; with the exported `Orion_CA` and the host name from the certificate it passes (by IP it fails with a host name mismatch, as expected). Python 3.13+ `VERIFY_X509_STRICT` would reject the Orion CA (no Key Usage extension); the CLI drops that single flag for the CA given with `-e` and keeps it for the system store. Upstream still defaults to no verification. |
| **ECDSA client certificates** | ePO 5.10 signs an EC P-256 CSR from `provisionconfig --key-type ec` without complaint, but a DXL 6.1.3 broker then rejects the TLS handshake (`handshake_failure`): its CertificateRequest lists only `RSA sign` with `RSA+SHA256/384/512`. Until the broker side changes, use RSA — RSA-3072 (`--key-bits 3072`) is signed and accepted end-to-end (measured 2026-09-07). |
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
