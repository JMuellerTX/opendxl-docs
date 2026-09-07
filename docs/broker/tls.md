# TLS and ciphers

This is the single most common reason a DXL client that used to work stops working, and the
first thing to check when a connection fails without a useful error message.

## The problem in one paragraph

OpenDXL brokers, and Trellix DXL brokers before version 6.1.1, offer **only RSA
key-transport cipher suites** — every suite on the listener is a `TLS_RSA_*` one, so **no
connection to them has forward secrecy**. Between roughly 2021 and 2024 every major runtime
dropped `TLS_RSA_*` from its defaults as a class. A current client and an old broker therefore
share no cipher, and the TLS handshake fails.

A scan of the published `opendxl/opendxl-broker` image finds eight TLS 1.2 suites:

```
TLS_RSA_WITH_AES_256_GCM_SHA384      TLS_RSA_WITH_AES_256_CBC_SHA256
TLS_RSA_WITH_AES_128_GCM_SHA256      TLS_RSA_WITH_AES_256_CBC_SHA
TLS_RSA_WITH_CAMELLIA_256_CBC_SHA    TLS_RSA_WITH_AES_128_CBC_SHA256
TLS_RSA_WITH_CAMELLIA_128_CBC_SHA    TLS_RSA_WITH_AES_128_CBC_SHA
```

No TLS 1.3, and no ECDHE or DHE anywhere. `AES128-SHA256`
(`TLS_RSA_WITH_AES_128_CBC_SHA256`) gets named most often because it is the one the OpenDXL
clients pin, but pinning a different one from that list does not help — the whole list is the
problem.

## Symptoms per runtime

| Runtime | What you see |
|---|---|
| **Python 3.10+** | `ssl.SSLError: [SSL: SSLV3_ALERT_HANDSHAKE_FAILURE]`, or a `connect()` that never succeeds and retries forever because `ConnectRetries` defaults to `-1` |
| **Java 11+ (current updates)** | `SSLHandshakeException`. JSSE reads `jdk.tls.disabledAlgorithms` once at initialization, so the application cannot re-enable `TLS_RSA_*` for its own sockets — see [Java client](../clients/java.md#tls-on-current-jdks) |
| **Node.js 18+** | `ERR_SSL_...` / handshake failure from the TLS socket |

In all three the failure is at the transport layer, before any DXL message exists, so nothing
in the DXL logs explains it. Confirm what the broker actually offers:

```bash
openssl s_client -connect broker:8883 -tls1_2 -cipher 'ALL' </dev/null 2>/dev/null \
  | grep -E 'Cipher|Protocol'
```

List everything a broker offers, rather than just what one client negotiates:

```bash
nmap -Pn -sT --script ssl-enum-ciphers -p 8883 broker
```

A broker whose list is entirely `TLS_RSA_*`, with a "Forward Secrecy not supported by any
cipher" warning, is the old profile.

## Fixing it on the broker

The right fix, because it removes the problem for every client at once.

**Root cause in the open source broker:** `WITH_EC` is never defined at build time, so
elliptic-curve support is compiled out of the mosquitto-derived core. The `ciphers=` setting
can list ECDHE suites all it wants; the binary cannot negotiate them. Rebuilding with
`WITH_EC` defined — which also means building against OpenSSL 3 on a maintained base image —
is what actually widens the cipher list.

The [maintained broker fork](../fork.md) exposes three profiles through the environment:

| `DXL_TLS_MODE` | Cipher list | Models |
|---|---|---|
| `modern` (default) | `ECDHE+AESGCM:ECDHE+AES:DHE+AES:AES128-SHA256:!aNULL:!eNULL:!MD5:!3DES` | Trellix DXL ≥ 6.1.1: forward secrecy first, legacy suite as fallback |
| `legacy` | `AES128-SHA256:AES256-SHA256:AES128-GCM-SHA256:AES256-GCM-SHA384:!aNULL:!eNULL` | DXL brokers before 6.1.1 — for reproducing the old behaviour on purpose |
| `pfs-only` | `ECDHE+AESGCM:ECDHE+AES:DHE+AES:!aNULL:!eNULL:!MD5:!3DES` | A FIPS-140-3-oriented profile with no RSA key transport at all |
| `trellix-6.1` | the twelve suites listed below | Exactly what a Trellix DXL 6.1.3.55 broker presents, measured against a live fabric. Use this to test against production rather than a superset of it |

`DXL_TLS_CIPHERS` overrides the list with an explicit OpenSSL cipher string. An explicit
`ciphers=` line in `dxlbroker.conf` still wins over both.

`modern` is the profile to run in a mixed estate: current clients negotiate ECDHE, and an old
client that only knows `AES128-SHA256` still connects.

`trellix-6.1` is the one to *test* against. `modern` is deliberately a superset — it also
offers DHE, which the Trellix broker does not — so a client that works against `modern` may
still be relying on something production will not give it:

```
ECDHE (secp256r1)                       RSA key transport
  ECDHE-RSA-AES256-GCM-SHA384             AES256-GCM-SHA384   AES256-SHA256
  ECDHE-RSA-AES128-GCM-SHA256             AES128-GCM-SHA256   AES256-SHA
  ECDHE-RSA-AES256-SHA384                 CAMELLIA256-SHA     AES128-SHA256
  ECDHE-RSA-AES128-SHA256                 CAMELLIA128-SHA     AES128-SHA
```

## TLS 1.3, and post-quantum key exchange

The broker code used to ask OpenSSL for `TLSv1_2_server_method()`, which pins the listener to
TLS 1.2 whatever the library underneath can do. Built against OpenSSL 4.0.2 and asking for a
protocol range instead, the fork's broker offers:

```
TLSv1.3   TLS_AES_256_GCM_SHA384, TLS_AES_128_GCM_SHA256,
          TLS_CHACHA20_POLY1305_SHA256      group: X25519MLKEM768
TLSv1.2   15 suites (ECDHE over x25519, DHE, AES128-SHA256 as the fallback)
```

`X25519MLKEM768` is a **hybrid post-quantum key exchange**: classical X25519 combined with
ML-KEM-768, so a session recorded today is not decryptable by a future quantum computer unless
*both* halves fall. It comes free with OpenSSL 4 once the listener stops pinning the protocol
version.

No Trellix DXL broker offers TLS 1.3 — the 6.1.x line is on OpenSSL 1.0.2zk. The practical use
of this is therefore testing: it is somewhere to exercise a client's TLS 1.3 path before the
commercial brokers get there. `tls_version=tlsv1.3` in `dxlbroker.conf` pins the listener to
1.3 only, which is the configuration to test that path deliberately.

## Fixing it on the client

When you cannot change the broker.

**Python** — set the cipher list in `dxlclient.config`:

```ini
[General]
TlsCiphers=ECDHE+AESGCM:ECDHE+AES:DHE+AES:AES128-SHA256:!aNULL:!eNULL
TlsMinVersion=1.2
```

`TlsCiphers` and `TlsMinVersion` are additions of the [maintained fork](../fork.md); the
released 5.7.0.1 package has neither, and re-enabling the suite there means patching the
`ssl` context by hand.

**Java** — see [Java client](../clients/java.md#tls-on-current-jdks). The in-process fix is
`TlsCompatibility` in the [maintained fork](../fork.md); the runtime-level fix is
`-Djava.security.properties=<file>` with `TLS_RSA_*` removed from `jdk.tls.disabledAlgorithms`.
The fork's Java client also understands `TlsCiphers`, but as a comma separated list of JSSE
cipher suite names (`TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,...`), not as an OpenSSL cipher
list — JSSE has no equivalent of the OpenSSL syntax. An OpenSSL value in a shared
configuration file is ignored with a warning. See
[Java client](../clients/java.md#tlsciphers-is-not-an-openssl-cipher-list).

**Node.js** — pass the cipher list to the TLS socket options, or start node with
`--tls-cipher-list`.

Re-enabling `AES128-SHA256` on the client is a deliberate downgrade: that connection has no
forward secrecy, so a future compromise of the broker's private key exposes recorded traffic
retroactively. It is an acceptable bridge while brokers are upgraded and a bad permanent
state.

## Minimum TLS version

`TlsMinVersion` defaults to **1.2** in the fork's Python client. There is no reason to go
below it: TLS 1.0 and 1.1 are deprecated, and no DXL broker requires them.

TLS 1.3 is a different question. Trellix DXL 6.1.x brokers run on OpenSSL 1.0.2zk and cannot
offer TLS 1.3 at all, so 1.2 remains the negotiated version against them. ePolicy Orchestrator
5.10 SP1 Update 7 moved to OpenSSL 3.5.7 and does offer TLS 1.3 — but that is the *management*
service (`https://epo:8443/remote`, used by `provisionconfig`), not the broker's MQTT
listener.

## Certificates

- Client certificates are signed by the fabric CA. The client presents one on every
  connection; it is its identity for [topic authorization](../concepts/topics-and-authorization.md).
- CSRs are signed **SHA-256** by default, with RSA-2048 keys. Under FIPS 140-3 profiles,
  RSA-3072 or ECDSA P-256 may be required — the fork's CLI takes `--key-type`,
  `--key-bits` and `--key-curve` for that. Measured on 2026-09-07 against ePO 5.10 with a
  DXL 6.1.3.55 broker: **RSA-3072 is signed and connects** (TLS 1.2,
  `ECDHE-RSA-AES256-GCM-SHA384`); an **EC P-256 certificate is signed by ePO but refused by
  the broker** with `handshake_failure`, because the broker's CertificateRequest only offers
  the client certificate type `RSA sign` and the signature algorithms `RSA+SHA256/384/512`.
  ECDSA client identities need a broker-side change first.
- **Host name verification is off by default** (`VerifyHostname=false`), and on current
  fabrics it has to be. A Trellix DXL 6.1.3.55 broker presents a certificate with
  **`CN=localhost` and no subjectAltName at all**, while publishing itself as a fully
  qualified host name. Switching verification on against such a broker fails every
  connection. ePO 5.10 SP1 U7's custom SAN support applies to agent-handler certificates,
  not to the broker certificate a DXL client validates — so it does not change this.
  Turn verification on only where you have checked that the broker certificate actually
  carries the name you connect to.

## Checklist when a connection fails

1. `openssl s_client -connect broker:8883` — does the handshake complete at all, and with
   which suite?
2. If it fails: compare the broker's offered suites against the client runtime's defaults.
   That is the answer in most cases.
3. If it succeeds but the client does not connect: check the certificate paths in
   `dxlclient.config` and that the CA bundle matches the broker's CA.
4. If the client connects but sees nothing: it is not TLS — check
   [topic authorization](../concepts/topics-and-authorization.md) and the `broker_ids` /
   `client_ids` delivery filters on the messages.
