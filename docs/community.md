# Community and support

## Where to ask

**[Trellix Community](https://thrive.trellix.com/)** — the place for questions about DXL in a
Trellix deployment: broker versions, ePolicy Orchestrator, TIE, Active Response, and how
OpenDXL fits alongside them. It is where the people who run these fabrics are.

An OpenDXL board on that community is proposed and not yet created. Until it exists, ask in
the product board closest to your question and mention OpenDXL in the title.

**GitHub issues** — for a bug or a question about a specific repository, its own issue tracker
is the right place. Include the client version, the runtime version, the broker version, and
the actual error. Given the state of upstream maintenance
([history](history.md#what-stewardship-looks-like-now)), expect a slow answer or none, and
consider whether a fork already fixes what you found.

**[Open Cybersecurity Alliance](https://opencybersecurityalliance.org/)** — OpenDXL was
contributed to the OCA in 2019. The OCA is the venue for questions about interoperability
standards rather than about a particular client library. (As of this writing the OCA site's
TLS certificate has expired, so browsers warn before loading it.)

## The old forum

opendxl.com ran a forum from 2016 to about 2021. It is closed to new posts. Its threads were
largely product questions that the Trellix Community now covers, and version-specific issues
that no longer apply to anything you would deploy today. Nothing from it is reproduced here.

## Before you ask

Most connection problems have the same three causes, and checking them takes a minute:

1. **TLS.** `openssl s_client -connect broker:8883` — if the handshake fails, the answer is in
   [TLS and ciphers](broker/tls.md), and no amount of DXL configuration will help.
2. **Certificates.** Does `dxlclient.config` point at files that exist, and is the CA bundle
   the one that signed the broker's certificate?
3. **Authorization.** A client that connects but receives nothing is usually a
   [topic authorization](concepts/topics-and-authorization.md) question, or a `broker_ids` /
   `client_ids` filter left set on the message.

Turn on debug logging before you write the question — it usually answers it:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

See [Contributing](contributing.md). This documentation is Apache-2.0 and lives in its own
repository; corrections are welcome and are the cheapest contribution to make.
