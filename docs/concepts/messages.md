# Messages and payloads

Every DXL message shares one envelope and differs only in type and a few type-specific
fields. Understanding the envelope explains most of what the client libraries do.

## The envelope

| Field | Set by | Purpose |
|---|---|---|
| `version` | library | Message format version — decides which optional fields are present |
| `message_id` | library | UUID; correlates a response to its request |
| `source_client_id` | library | The sending client's identity — the **SHA-1 thumbprint of its certificate**, not the `ClientId` from its configuration; see below |
| `source_broker_id` | broker | Which broker the message entered the fabric through |
| `broker_ids` | caller | Optional: restrict delivery to these brokers |
| `client_ids` | caller | Optional: restrict delivery to these clients |
| `payload` | caller | Opaque bytes — the actual content |
| `destination_topic` | caller | The topic |

`broker_ids` and `client_ids` are delivery filters, not authorization. Leave them empty unless
you have a specific reason; narrowing delivery is a common source of "the subscriber never
gets anything" bugs.

### Who a message is from

The `ClientId` a client writes into its configuration never reaches the fabric. Measured
against the open source broker and against a Trellix DXL broker 6.1.3 alike:

- `source_client_id` on every message a client publishes is the **SHA-1 thumbprint of the
  client's certificate** (lowercase hex, no colons) — the same value the broker's topic
  authorization is written against.
- Registry payloads carry the same thumbprint as `clientGuid`, and a per-connection identity
  as `clientInstanceGuid` in the form `<thumbprint>:<instance guid>`; the instance guid changes
  with every connection.
- Events the broker itself publishes (service registry, connect events) carry the **broker's**
  GUID as `source_client_id`.

So identity on a DXL fabric is the certificate, and two clients provisioned with the same
certificate are the same identity. Correlate connect events, registrations and published
messages on the thumbprint, never on the configured `ClientId`.

## Encoding

The envelope is [MessagePack](https://msgpack.org/), a compact binary format. Clients do not
hand-encode it — the library packs and unpacks. What matters to an integration author is that
the `payload` is a **byte string**, and the encoding of its contents is a contract between
the service and its callers, not something DXL enforces.

The convention across the reference integrations is UTF-8 encoded JSON:

```python
import json
request.payload = json.dumps({"hashes": [{"type": "md5", "value": "…"}]}).encode("utf-8")
…
result = json.loads(response.payload.decode("utf-8"))
```

Nothing stops a service from using Protobuf, CBOR or raw bytes; it just has to say so in its
[API specification](../repositories.md#specifications-and-schemas).

## Payload size

Brokers enforce a maximum message size (`messageSizeLimit` on the broker side, 1 MiB by
default in the open source broker). Payloads above that are rejected by the broker, not
truncated. Two consequences:

- **Bulk data does not belong in a DXL message.** Publish a reference — an object store key,
  a URL, a query handle — and let the consumer fetch it.
- **A service that grew past the limit fails abruptly** when a particular input produces a
  larger response than usual. Services returning variable-length results should paginate.

## Message versions and interoperability

The `version` field lets newer clients add fields without breaking older peers: an old client
unpacks the fields it knows and ignores the rest. In practice, a current OpenDXL client talks
to a 2016-era broker and vice versa. The compatibility risks in this ecosystem are not in the
message format — they are in TLS (see [TLS and ciphers](../broker/tls.md)) and in the
MessagePack library version used by the Python client (see
[Compatibility](../compatibility.md)).

## Errors

`ErrorResponse` is a `Response` with an error code and message. A service returns it instead
of a normal response when it cannot fulfil the request:

```python
from dxlclient.message import ErrorResponse

def on_request(self, request):
    try:
        result = do_work(request.payload)
    except LookupError as exc:
        self._client.send_response(ErrorResponse(request, error_code=404,
                                                 error_message=str(exc)))
        return
    …
```

On the caller side an error response is a **normal return value**, not an exception —
`sync_request` raises only on timeout and transport failures. Always check the type:

```python
from dxlclient.message import Message

response = client.sync_request(request, timeout=30)
if response.message_type == Message.MESSAGE_TYPE_ERROR:
    raise RuntimeError("service error %s: %s" %
                       (response.error_code, response.error_message))
```

Skipping that check is the single most common bug in DXL integrations: the error message ends
up being parsed as if it were a successful payload.
