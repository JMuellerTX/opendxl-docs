# Java client

Artifact `com.opendxl:dxlclient`. Feature parity with the Python client for messaging;
provisioning is done with the Python CLI or ePolicy Orchestrator, then the resulting
`dxlclient.config` is read by the Java client.

- Upstream: [opendxl/opendxl-client-java](https://github.com/opendxl/opendxl-client-java)
- API documentation: [opendxl.github.io/opendxl-client-java](https://opendxl.github.io/opendxl-client-java/docs/javadoc/index.html)

## Connect

```java
DxlClientConfig config = DxlClientConfig.createDxlConfigFromFile("config/dxlclient.config");
try (DxlClient client = new DxlClient(config)) {
    client.connect();
    // ...
}
```

`DxlClient` implements `AutoCloseable`; the try-with-resources block disconnects and shuts
down the client's executors.

## Events

```java
client.addEventCallback("/isv/acme/event/verdict", event ->
        System.out.println(new String(event.getPayload(), StandardCharsets.UTF_8)));

Event event = new Event("/isv/acme/event/verdict");
event.setPayload(json.getBytes(StandardCharsets.UTF_8));
client.sendEvent(event);
```

## Requests

```java
Request request = new Request("/isv/acme/service/sandbox/detonate");
request.setPayload(payload);
Response response = client.syncRequest(request, 30_000);   // milliseconds

if (response.getMessageType() == Message.MESSAGE_TYPE_ERROR) {
    ErrorResponse error = (ErrorResponse) response;
    throw new IllegalStateException(error.getErrorCode() + ": " + error.getErrorMessage());
}
```

Note the unit: `syncRequest` takes **milliseconds**, while the Python client's `timeout` is in
seconds. Porting code between the two without noticing produces either a 30-millisecond
timeout or a 30 000-second one.

## Services

```java
ServiceRegistrationInfo info = new ServiceRegistrationInfo(client, "/isv/acme/service/sandbox");
info.addTopic("/isv/acme/service/sandbox/detonate", request -> {
    Response response = new Response(request);
    response.setPayload(result);
    client.sendResponse(response);
});
client.registerServiceSync(info, 10_000);
```

## TLS on current JDKs

This is the one Java-specific pitfall, and it is a hard failure rather than a warning.

OpenDXL brokers — and Trellix DXL brokers before 6.1.1 — offer only TLS 1.2 cipher suites that
use **RSA key exchange**, for example `TLS_RSA_WITH_AES_128_CBC_SHA256`. Current JDK updates
list `TLS_RSA_*` in the `jdk.tls.disabledAlgorithms` security property (JDK-8245545). JSSE
reads that property **once**, when it initializes, and applies it on top of whatever cipher
suites a socket enables — so an application cannot re-enable those suites for its own
connections.

The symptom is a TLS `handshake_failure` on every connection attempt; and because
`connectRetries` defaults to `-1`, the client then retries forever instead of failing.

The [maintained fork](../fork.md) handles this in `TlsCompatibility`, which removes the `TLS_RSA_*` entry
from the security property before JSSE is first used. Opt out when every broker in reach
supports ECDHE:

```
-Ddxlclient.tls.enableRsaKeyExchange=false
```

If your application initializes TLS before creating the first `DxlClient`, the in-process fix
comes too late. Start the JVM with an adjusted security properties file instead:

```
-Djava.security.properties=/path/to/dxl.security
```

containing a `jdk.tls.disabledAlgorithms` value without `TLS_RSA_*`.

The durable fix is on the broker side: a broker that offers ECDHE needs none of this. See
[TLS and ciphers](../broker/tls.md).

## TLS 1.3, `TlsMinVersion` and `VerifyHostname`

The upstream client obtains its context with `SSLContext.getInstance("TLSv1.2")`, which pins
every connection to TLS 1.2 no matter what the broker offers. The [maintained fork](../fork.md)
creates the context for `"TLS"` and applies a floor per socket instead, so a broker that offers
TLS 1.3 — the fork's own broker does — is used at TLS 1.3, and older brokers still negotiate 1.2.
Two keys in the `[General]` section of `dxlclient.config` match the Python client's spelling
and defaults:

| Key | Default | Meaning |
|---|---|---|
| `TlsMinVersion` | `1.2` | Lowest TLS version the client accepts; `1.3` or the JSSE names (`TLSv1.3`) are accepted too |
| `VerifyHostname` | `false` | `true` sets the HTTPS endpoint-identification algorithm; off by default because broker certificates on current fabrics carry `CN=localhost` and no SAN |

The floor is built from the protocols the JDK actually reports, so a Java 8 runtime older than
8u261 (no TLS 1.3) simply negotiates TLS 1.2 instead of failing. The change is on all four
branches (`master`, `jdk17`, `jdk11`, `jdk8`) and was verified with the client test suite
against a broker on each line.

## Provisioning CLI: certificate validation and key size

`java -jar dxlclient-all.jar provisionconfig|updateconfig` talks to the management service
over HTTPS. Upstream, the CLI accepted any server certificate and skipped host name
verification unless `-e/--truststore` was given, and `-e` itself never worked: the option's
value, the file name, was handed to the certificate parser as if it were the PEM content
(`No certificate data found`). The [maintained fork](../fork.md) fixes both and mirrors the
Python CLI:

| Option | Behaviour |
|---|---|
| none | Validate against the JVM's trusted CAs, with host name verification. Against an ePO server this fails, with a message that names the fix, because the ePO web certificate comes from the server's own CA |
| `-e/--truststore FILE` | Validate against the CAs in the PEM file; the file must exist. Address the server by the host name in its certificate, not by IP |
| `--insecure` | Accept any certificate (the old default); refused together with `-e` |
| `--key-bits 2048\|3072\|4096` | RSA key size of the generated private key (was fixed at 2048). No EC option on purpose: DXL brokers up to 6.1.3 refuse ECDSA client certificates |

Verified against a broker container with JDK 21; the change is on all four branches.

## JDK versions

The upstream releases target Java 8. The [maintained fork](../fork.md) keeps one branch per JDK line —
`master` (JDK 21), `jdk17`, `jdk11`, `jdk8` — because the Gradle toolchain, the foojay
resolver and the test rules differ enough between them that a single build cannot cover all
four. Fixes land on `master` and are cherry-picked downwards.
