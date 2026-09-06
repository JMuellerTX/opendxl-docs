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

## JDK versions

The upstream releases target Java 8. The [maintained fork](../fork.md) keeps one branch per JDK line —
`master` (JDK 21), `jdk17`, `jdk11`, `jdk8` — because the Gradle toolchain, the foojay
resolver and the test rules differ enough between them that a single build cannot cover all
four. Fixes land on `master` and are cherry-picked downwards.
