# Topics and authorization

## Topic naming

Topics are slash-separated strings. There is no registry and no enforced grammar, so the
convention carries the weight:

```
/<owner>/<kind>/<product>/<capability>[/<detail>]

/mcafee/service/tie/file/reputation      request topic of the TIE reputation service
/mcafee/event/tie/file/repchange         event published when a reputation changes
/isv/acme/service/sandbox/detonate       a third-party service
/isv/acme/event/sandbox/verdict          its result event
```

Three rules keep a fabric maintainable:

1. **Namespace by owner.** `/mcafee/…` belongs to the platform; publish your own under
   `/isv/<yourname>/…` or a domain you control. Squatting in someone else's namespace makes
   topic authorization unwritable.
2. **Separate `service` from `event` in the path.** It makes policy rules and dashboards
   readable at a glance, and it prevents a request topic from being accidentally subscribed
   to as a broadcast.
3. **Do not encode volatile values in the topic** — no hostnames, no hashes, no tenant IDs.
   Those belong in the payload. Topics are policy surface; a topic per host means a policy
   per host.

Wildcard subscriptions follow MQTT: `#` matches the remainder of a path. Subscribing to `#`
on a production fabric means receiving every event on it, which is occasionally the right
diagnostic and never the right integration.

## Authorization model

Authorization is enforced by the broker, per topic, against the **thumbprint of the client
certificate** — or of a CA in the client's chain, which lets one rule cover every client
issued by that CA.

The open source broker reads `topicauth.policy`. Topics are **open by default**; the file
lists the exceptions:

```json
{
    "send": [
        {
            "topic": "/isv/acme/service/sandbox/detonate",
            "clients": [
                "0a97b7282ab8fc30a1be704ed6c208fb7637ddeb"
            ]
        }
    ],
    "receive": [
        {
            "topic": "/isv/acme/event/sandbox/verdict",
            "clients": [
                "ba8f5dd8763143444a86fefeecd3eb7b4aa2fe4f"
            ]
        }
    ]
}
```

`send` restricts who may publish; `receive` restricts who may subscribe. Both are allow-lists:
once a topic appears in a list, only the named thumbprints (or CA-signed clients) may use it
in that direction.

"Open by default" is a deliberate design for a lab broker and a deliberate risk in
production. On a managed Trellix DXL fabric the same model is administered centrally through
ePolicy Orchestrator rather than a file.

## Getting a thumbprint

```bash
openssl x509 -in client.crt -noout -fingerprint -sha1 \
  | sed 's/.*=//; s/://g' | tr 'A-Z' 'a-z'
```

Lowercase, no colons — the format the policy file expects.

## Practical policy shape

For an integration you are deploying, three rules cover the normal case:

- The **service** may `send` on its own event topics and is the only client allowed to
  `receive` on its request topics — so nobody else can register a competing service under
  your name.
- The **callers** are allowed to `send` on the request topic.
- Everything else stays open, or the fabric closes it globally.

Write the rules against the **CA thumbprint** where a group of clients shares an issuing CA;
write them against individual client thumbprints only where the identity really is
individual. Per-client rules are what turn a policy file into something nobody dares to
change.

## What authorization does not do

- It does not authenticate *users* — only clients. If a service acts on behalf of a human,
  the service is responsible for that, in its payload contract.
- It does not encrypt payloads beyond the TLS transport. Everyone allowed to receive on a
  topic sees the full payload.
- It does not rate-limit. A client permitted to publish may publish as fast as it can.
