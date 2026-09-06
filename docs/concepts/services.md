# Services and requests

A DXL service is an ordinary client that has told the fabric "I answer requests on these
topics". Everything else — discovery, routing, load balancing, failover — follows from the
registration.

## Registration

```python
from dxlclient.service import ServiceRegistrationInfo

info = ServiceRegistrationInfo(client, "/isv/example/service")
info.add_topic("/isv/example/service/lookup", LookupCallback(client))
info.add_topic("/isv/example/service/submit", SubmitCallback(client))
info.ttl = 60                                    # minutes
info.add_metadata("version", "1.2.0")
client.register_service_sync(info, timeout=10)
```

The first argument is the **service type** — a name shared by all instances of the same
service. The topics are what callers address. Metadata is arbitrary key/value data that
consumers can read from the service registry.

Registration is itself a DXL message, sent to `/mcafee/service/dxl/svcregistry/register`, and
the fabric announces it as an event on `/mcafee/event/dxl/svcregistry/register`. A client can
subscribe to those events to learn when services appear and disappear.

## Time to live

A registration carries a TTL and the client library renews it in the background. If the
process dies, the registration expires and the fabric stops routing to it — there is no
separate health check and no stale entry to clean up by hand.

The trade-off is latency of failure detection: with a 60-minute TTL, a crashed instance may
receive routed requests for up to an hour if the broker did not notice the connection drop.
Broker-side disconnect detection normally deregisters much sooner; the TTL is the backstop.
Shorter TTLs detect failure faster at the cost of more registration traffic.

Deregister explicitly on clean shutdown:

```python
client.unregister_service_sync(info, timeout=10)
```

## Load balancing and idempotence

When several instances register the same service type and topics, the fabric routes each
request to **one** of them. Which one is not specified and must not be relied on. This means:

- A service must be **idempotent** or must partition work by something in the request,
  not by which instance received it.
- **In-memory state is per instance.** Caches, rate-limit counters and sessions do not carry
  across instances. If a caller's second request needs the state from its first, either keep
  the state in a shared store or model the interaction as a single request.

## Threading

Request callbacks run on the client's callback threads, not on the main thread. Two rules
follow:

- **Never block a callback for long.** The pool is bounded (`incoming_message_thread_pool_size`,
  default 1 in the Python client) and a slow handler stalls every other message for that
  client. Hand long work to your own executor and respond when it finishes.
- **Guard shared state.** Two requests can be in two callbacks at the same time when the pool
  is larger than one.

## Timeouts

The caller sets the timeout; the service does not know it. A service that takes longer than
the caller allows does its work anyway and sends a response nobody is waiting for. If a
service can be slow, publish its expected latency in its API specification so callers can pick
a sane timeout, and consider an event-based "job accepted / job finished" design instead of a
long synchronous request.

## Asynchronous requests

`sync_request` blocks the calling thread. For fan-out, use the asynchronous form and let the
library correlate responses:

```python
from dxlclient.callbacks import ResponseCallback

class Collect(ResponseCallback):
    def on_response(self, response):
        handle(response)

client.async_request(request, Collect())
```

The callback fires on a client thread, with the same rules as above.

## Writing a service that other people can use

- **Namespace the topic.** `/<vendor>/<product>/<capability>` keeps the fabric readable and
  makes topic authorization writable. Do not publish under `/mcafee/…` — that namespace
  belongs to the platform.
- **Version the contract, not the topic.** Adding an optional field is compatible; removing or
  retyping one is not. When you must break, add a new topic rather than changing the old one.
- **Return `ErrorResponse`, not a payload that says "error".** Callers check the message type;
  see [Messages and payloads](messages.md#errors).
- **Publish an API specification.** See [Repositories](../repositories.md#specifications-and-schemas).

The [OpenDXL bootstrap](../repositories.md#tooling-and-scaffolding) generator produces a
service skeleton with configuration handling, logging and the registration lifecycle already
wired up — it is the fastest correct starting point.
