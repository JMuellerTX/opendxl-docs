# Security guidance

A DXL fabric carries security telemetry and lets clients invoke actions on production systems.
This page collects the decisions that matter, in the order they usually go wrong.

## Identity is the certificate

There is no username or password on the fabric. A client is its certificate, and everything
else — topic authorization, audit, revocation — hangs off that.

- **Provision one certificate per workload**, not one shared certificate for a fleet. A shared
  certificate cannot be revoked without taking everything down, and topic policy written
  against it cannot distinguish the workloads.
- **Protect the private key.** `provisionconfig` writes an unencrypted key unless you pass
  `-P/--passphrase`. Anything that can read `client.key` can act as that client on the fabric.
- **Never commit the config directory.** `client.key`, `client.crt` and `dxlclient.config`
  belong in `.gitignore` in any project that provisions into its working tree. The failure
  mode is not theoretical: a certificate in a public repository is a working fabric identity
  until someone revokes it.
- **Plan revocation before you need it.** Know who runs the CA — the broker in a lab,
  ePolicy Orchestrator in a managed fabric — and how a certificate is revoked there.

## Transport

TLS 1.2 minimum, forward secrecy where the fabric allows it. The details, including why an
old broker forces a downgrade and what that costs you, are in
[TLS and ciphers](broker/tls.md).

Two points deserve repeating here:

- **`AES128-SHA256` has no forward secrecy.** A future compromise of the broker's private key
  exposes previously recorded traffic. Using it to reach an old broker is a reasonable bridge;
  leaving it enabled after the broker is upgraded is not.
- **Host name verification is off by default** (`VerifyHostname=false`). With it off, a client
  that reaches the wrong host — through DNS, a proxy, or a hostile network — still completes
  the handshake as long as the certificate chains to the fabric CA. Turn it on where the
  broker certificates carry names that match how you address them.

## Authorization

Topics are **open by default** on the open source broker. On a fabric that carries anything
real, that default is the risk, not a convenience.

Write policy for at least:

- **Your service's request topics** — restricted to your service's certificate, so no one else
  can register a competing service under your name and receive your callers' requests.
- **Sensitive event topics** — restricted to the consumers that need them. Everyone allowed to
  receive on a topic sees the full payload; there is no per-field access control.

Details and the file format are in
[Topics and authorization](concepts/topics-and-authorization.md).

## Payloads

- **Do not put third-party credentials in DXL messages.** A service that wraps an API holds
  that API key in its own configuration. Passing it through the fabric spreads it to everyone
  with receive rights on the topic.
- **Validate incoming payloads.** A request callback runs on data from another client. Parse
  defensively; do not pass payload fields into a shell, a query, or a file path unchecked.
- **Do not carry bulk data.** Above the broker's `messageSizeLimit` (1 MiB by default) the
  message is rejected. Publish a reference and let the consumer fetch it.

## Operational

- **`connect_retries` defaults to `-1`.** A client with a wrong certificate or an
  unreachable broker retries forever and looks like a hang. Set a finite value so
  misconfiguration is visible.
- **A service TTL is your failure detector.** A registration that stops being renewed expires.
  Shorter TTLs detect a dead instance faster at the cost of more registration traffic.
- **Log the message ID.** It is the only correlation handle between a caller and a service
  across the fabric.

## Known-vulnerable dependencies

The published packages carry known advisories — `msgpack` 0.6.2 in the Python line, `ws` 6.2.1
via `mqtt` 2.x in the JavaScript line, older jackson-databind and BouncyCastle in the Java
line. [Compatibility](compatibility.md) lists what has been fixed where.

Generate an SBOM for whatever you actually ship and check it against an advisory database.
For these projects that is not optional hygiene — the transitive trees are five years old.

## Package names are a security boundary

The coordinates a build file resolves are part of the attack surface, and for Java they are
tied to a domain name. Maven Central verifies a namespace by asking the publisher to place a
**DNS TXT record on the matching domain**: `com.opendxl` is proven by control of
`opendxl.com`. Whoever holds that domain can claim the namespace and publish *new* versions
under coordinates that existing builds already resolve — `com.opendxl:dxlclient`,
`com.opendxl:dxldatabusclient`, `com.opendxl:dxlstreamingclient`. Published artifacts on
Central are immutable, so this is not about rewriting the past; it is about the next version.

This is a known class of attack, not a thought experiment:

- **MavenGate** (Oversecured, January 2024) checked 33,938 domains behind Maven group IDs and
  found 6,170 — **18%** — expired or purchasable, `com.opencsv` and `net.jpountz.lz4` among
  them. Sonatype disagreed that the attack is practical given its automation, and disabled
  accounts tied to expired domains anyway; a detailed rebuttal argues the methodology
  overcounted. The residual risk both sides agree on is the one above: new versions under
  existing coordinates.
- **`ctx` on PyPI and `phpass` on Packagist** (May 2022): a maintainer's domain expired, an
  attacker re-registered it for a few dollars, received the password-reset mail and published
  credential-stealing versions of a package that had been untouched for eight years.
- PyPI now re-checks the domains behind maintainer e-mail addresses every 30 days and has
  marked **over 1,800** addresses unverified since June 2025 — registries treat domain expiry
  as an attack vector, not as paperwork.
- The same shape one level up is **repojacking**: a renamed GitHub organisation frees its old
  name, and every `github.com/<old-name>/<repo>` reference — including the `scm` and `url`
  fields the OpenDXL Java client writes into its POM — can be pointed somewhere else.

Two consequences for anyone working with these projects:

- **If you consume OpenDXL artifacts**, pin versions, verify signatures where they exist, and
  keep an SBOM. A coordinate you have resolved for years is not automatically the same
  publisher.
- **The maintained fork does not publish under `com.opendxl`, `@opendxl` or the PyPI name
  `dxlclient`** — those namespaces belong to the upstream project, and a fork that occupied
  them would be indistinguishable from the attack described above. Fork builds are consumed
  from git or from the fork's own releases, and the Python client marks itself
  `5.7.0.1+fork.1` so an installed environment can tell which one it has.

## Reporting a vulnerability

For a vulnerability in a Trellix product, follow
[Trellix's disclosure process](https://www.trellix.com/about/legal/). For a vulnerability in
an OpenDXL repository, open an issue in that repository — and read
[history](history.md#what-stewardship-looks-like-now) first, so your expectation of a
coordinated fix matches the actual state of upstream maintenance.
