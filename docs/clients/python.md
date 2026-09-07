# Python client

Package `dxlclient`. The reference implementation and the most complete of the four clients:
it is the only one that ships the provisioning CLI.

- Upstream: [opendxl/opendxl-client-python](https://github.com/opendxl/opendxl-client-python)
- API documentation: [opendxl.github.io/opendxl-client-python](https://opendxl.github.io/opendxl-client-python/pydoc/)
- Latest released version: 5.6.0.4 (2020) — see [Compatibility](../compatibility.md) before pinning it

## Install

```bash
pip install dxlclient
```

## Configuration

Everything the client needs comes from `dxlclient.config`, produced by
[provisioning](../getting-started.md#3-provision-a-client-certificate):

```python
from dxlclient.client_config import DxlClientConfig
config = DxlClientConfig.create_dxl_config_from_file("./config/dxlclient.config")
```

The settings that matter most in practice:

| Property / config key | Default | Notes |
|---|---|---|
| `connect_retries` / `ConnectRetries` | `-1` | `-1` retries forever. Set a finite value if startup must fail fast. |
| `incoming_message_thread_pool_size` | `1` | Callbacks are serialized at the default. Raise it if handlers are slow — and then guard shared state. |
| `keep_alive_interval` | 1800 s | MQTT keep-alive |
| `reconnect_delay` / `_max` | 1 s / 60 s | Exponential backoff between reconnects |
| `TlsMinVersion` | `1.2` | Minimum TLS version. Added in the [maintained fork](../fork.md); see [TLS](../broker/tls.md). |
| `TlsCiphers` | `ECDHE+AESGCM:ECDHE+AES:DHE+AES:AES128-SHA256:!aNULL:!eNULL` | OpenSSL cipher string. Also fork-added. |
| `VerifyHostname` | `false` | Broker host name verification. Off by default for compatibility. |

`TlsMinVersion`, `TlsCiphers` and `VerifyHostname` do not exist in the released 5.6.0.4
package — they come from the [maintained fork](../fork.md).

## Lifecycle

`DxlClient` is a context manager, and using it as one is the difference between a clean
shutdown and leaked threads:

```python
from dxlclient.client import DxlClient

with DxlClient(config) as client:
    client.connect()
    ...
# disconnected, network thread stopped, callbacks unregistered
```

Without the `with` block, call `client.destroy()` in a `finally`. A client that is only
garbage-collected can leave its connection and its retry thread running.

## Events

```python
from dxlclient.callbacks import EventCallback
from dxlclient.message import Event

class MyCallback(EventCallback):
    def on_event(self, event):
        print(event.destination_topic, event.payload.decode("utf-8"))

client.add_event_callback("/isv/acme/event/verdict", MyCallback())

event = Event("/isv/acme/event/verdict")
event.payload = b'{"verdict": "malicious"}'
client.send_event(event)
```

`add_event_callback` subscribes and registers the handler in one call. To subscribe without a
handler (rare), use `client.subscribe(topic)`.

## Requests

```python
from dxlclient.message import Message, Request

request = Request("/isv/acme/service/sandbox/detonate")
request.payload = b'{"sha256": "..."}'
response = client.sync_request(request, timeout=30)

if response.message_type == Message.MESSAGE_TYPE_ERROR:
    raise RuntimeError("%s: %s" % (response.error_code, response.error_message))
result = response.payload.decode("utf-8")
```

Checking `message_type` is not optional — see [Messages](../concepts/messages.md#errors).

Asynchronous form:

```python
from dxlclient.callbacks import ResponseCallback

class Collect(ResponseCallback):
    def on_response(self, response):
        ...

client.async_request(request, Collect())
```

## Services

See [Services and requests](../concepts/services.md) for registration, TTL and threading. The
short form:

```python
from dxlclient.service import ServiceRegistrationInfo

info = ServiceRegistrationInfo(client, "/isv/acme/service/sandbox")
info.add_topic("/isv/acme/service/sandbox/detonate", DetonateCallback(client))
client.register_service_sync(info, timeout=10)
...
client.unregister_service_sync(info, timeout=10)
```

## The CLI

```bash
python -m dxlclient generatecsr      CONFIG_DIR COMMON_NAME
python -m dxlclient provisionconfig  CONFIG_DIR HOST_NAME COMMON_OR_CSRFILE_NAME -u USER -p PASS
python -m dxlclient updateconfig     CONFIG_DIR HOST_NAME -u USER -p PASS
```

`provisionconfig` generates a key and CSR, sends the CSR to the management service (the broker
in a lab, ePolicy Orchestrator in a managed fabric), and writes the signed certificate plus
`dxlclient.config`. `updateconfig` refreshes the broker list of an existing configuration —
run it after brokers are added or removed.

Options worth knowing:

| Option | Purpose |
|---|---|
| `-s/--san NAME …` | Subject Alternative Names in the CSR |
| `-P/--passphrase [PASS]` | Encrypt the generated private key |
| `--key-type rsa\|ec`, `--key-bits`, `--key-curve` | Key type and strength for FIPS profiles (fork addition). Measured against ePO 5.10 / DXL 6.1.3: RSA-3072 works end-to-end; an EC key is signed by ePO but the broker refuses it in the handshake (it only requests RSA client certificates) — see [Compatibility](../compatibility.md#open-items) |
| `-e/--truststore FILE` | PEM file with the CA that issued the management service's certificate. Needed whenever that CA is private, which is the normal case: ePO issues its web certificate from its own server CA |
| `--insecure` | Skip certificate validation of the management service entirely (fork addition; not recommended) |
| `-t/--port` | Management service port (8443 by default) |

!!! note "The management service's certificate is validated by default (fork)"
    Upstream, `provisionconfig` and `updateconfig` without `-e` did **not** verify the
    management service's certificate — they only suppressed the warning. The fork validates
    against the system's trusted CAs by default, so against an ePO server the command now
    fails with a message that names the fix: export the ePO server CA and pass it with `-e`.
    Two details measured against ePO 5.10:

    - Address ePO by the host name in its certificate. By IP the check fails with a host name
      mismatch, and the error message says so.
    - Python 3.13+ verifies in `VERIFY_X509_STRICT` mode, which rejects the ePO server CA
      because it carries no Key Usage extension. The CLI drops that one flag for the CA you
      named with `-e` (you trust it explicitly); it stays in force for the system store.

    `--insecure` restores the old behaviour for the rare case where the CA is not available.
    `--key-type ec` now logs a warning, because DXL brokers up to 6.1.3 refuse ECDSA client
    certificates in the handshake.

## Logging

The client uses the standard `logging` module under the `dxlclient` logger:

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger("dxlclient").setLevel(logging.DEBUG)
```

At `DEBUG` it logs connection attempts, broker selection and message flow — the first place to
look when a connect hangs or a request times out.
