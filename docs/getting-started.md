# Getting started

This walks from nothing to two processes exchanging a DXL message on a local broker. It uses
the Python client because it has the shortest setup, but the shape is identical in
[Java](clients/java.md) and [JavaScript](clients/javascript.md).

You need Docker and Python 3.8 or newer.

## 1. Run a broker

The open source broker ships as a container image:

```bash
docker run -d --name dxlbroker \
  -p 8883:8883 -p 8443:8443 -p 8444:443 \
  opendxl/opendxl-broker
```

| Port | Protocol |
|---|---|
| 8883 | MQTT over TLS — what the clients use |
| 8443 | Management service — what `provisionconfig` talks to |
| 443 (mapped to 8444) | WebSockets over TLS |

The container starts its own certificate authority on first run, which is what makes the next
step self-contained.

!!! note "The published image is old"
    The image on Docker Hub was built in 2021 on Debian stretch with OpenSSL 1.0.2. Every
    cipher suite it offers uses RSA key transport, so no connection to it has forward secrecy
    — and recent Python, JDK and Node.js versions dropped that whole class from their
    defaults, so a stock modern client will fail the handshake against it.
    [TLS and ciphers](broker/tls.md) explains the problem and the ways around it. The
    [maintained fork](fork.md) builds a current image (OpenSSL 4, TLS 1.3, forward secrecy)
    in about 25 minutes — see [Building a current image](broker/index.md#building-a-current-image).

## 2. Install the client

```bash
python -m venv .venv
.venv/bin/pip install dxlclient        # Windows: .venv\Scripts\pip
```

## 3. Provision a client certificate

Provisioning asks the broker's management service to sign a certificate signing request and
writes the resulting configuration and key material into a directory:

```bash
python -m dxlclient provisionconfig ./config 127.0.0.1 client -u admin -p password
```

Afterwards `./config` holds:

```
config/
  dxlclient.config     # brokers, certificate paths, connection settings
  ca-bundle.crt        # the fabric CA
  client.crt           # this client's certificate — its identity on the fabric
  client.key           # its private key
```

`dxlclient.config` is a plain INI file. It is the single input to `DxlClientConfig` and it is
what you copy to another machine when you move the client:

```ini
[Certs]
BrokerCertChain=ca-bundle.crt
CertFile=client.crt
PrivateKey=client.key

[Brokers]
{broker-guid}={broker-guid};8883;broker-hostname;172.17.0.2

[General]
```

!!! warning "Treat the config directory as a secret"
    `client.key` is an unencrypted private key unless you passed `-P/--passphrase`, and the
    certificate is the client's full identity on the fabric. Never commit this directory.
    Add `*.key`, `*.crt` and `dxlclient.config` to `.gitignore` in any project that provisions
    into its working tree.

## 4. Subscribe to an event

```python
from dxlclient.client import DxlClient
from dxlclient.client_config import DxlClientConfig
from dxlclient.callbacks import EventCallback

TOPIC = "/isv/example/event"

class PrintCallback(EventCallback):
    def on_event(self, event):
        print("received:", event.payload.decode("utf-8"))

config = DxlClientConfig.create_dxl_config_from_file("./config/dxlclient.config")
with DxlClient(config) as client:
    client.connect()
    client.add_event_callback(TOPIC, PrintCallback())
    input("subscribed — press enter to quit\n")
```

`DxlClient` is a context manager; leaving the `with` block disconnects and releases the
network thread. Doing that explicitly matters more than it looks — a client that is only
garbage-collected leaves its connection and threads behind.

## 5. Publish an event

In a second terminal, against the same config directory:

```python
from dxlclient.client import DxlClient
from dxlclient.client_config import DxlClientConfig
from dxlclient.message import Event

config = DxlClientConfig.create_dxl_config_from_file("./config/dxlclient.config")
with DxlClient(config) as client:
    client.connect()
    event = Event("/isv/example/event")
    event.payload = "hello fabric".encode("utf-8")
    client.send_event(event)
```

The subscriber prints `received: hello fabric`. That is the whole event path: no
registration, no schema negotiation, no acknowledgement.

## 6. Register a service and call it

A service is a client that answers requests on a topic. The callback receives a `Request` and
sends back a `Response`:

```python
from dxlclient.callbacks import RequestCallback
from dxlclient.message import Response
from dxlclient.service import ServiceRegistrationInfo

class UpperCaseCallback(RequestCallback):
    def __init__(self, client):
        super(UpperCaseCallback, self).__init__()
        self._client = client

    def on_request(self, request):
        response = Response(request)
        response.payload = request.payload.decode("utf-8").upper().encode("utf-8")
        self._client.send_response(response)

with DxlClient(config) as client:
    client.connect()
    info = ServiceRegistrationInfo(client, "/isv/example/service")
    info.add_topic("/isv/example/service/upper", UpperCaseCallback(client))
    client.register_service_sync(info, 10)
    input("service registered — press enter to quit\n")
```

Calling it:

```python
from dxlclient.message import Request

with DxlClient(config) as client:
    client.connect()
    request = Request("/isv/example/service/upper")
    request.payload = "hello".encode("utf-8")
    response = client.sync_request(request, timeout=10)
    print(response.payload.decode("utf-8"))     # HELLO
```

`sync_request` raises on timeout, and a service-side failure comes back as an `ErrorResponse`
rather than an exception — check `response.message_type` before trusting the payload.

## Where to go next

- [Services and requests](concepts/services.md) — registration, TTL, error handling,
  load balancing across instances.
- [Messages and payloads](concepts/messages.md) — the wire format and payload conventions.
- [The Python client](clients/python.md) — configuration reference and the async API.
- [Integrations](integrations.md) — the ready-made services (TIE, ePO, VirusTotal, MISP, …)
  and their client libraries.
