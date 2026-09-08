# OpenDXL Documentation

Human-readable documentation for the [OpenDXL](https://github.com/opendxl) ecosystem: the
Data Exchange Layer fabric, its clients, the open source broker, and the reference
integrations.

This repository holds prose, not client code. It exists because the per-repository READMEs
answer "how do I install this" and nothing answers "how does the fabric work, which client
line do I need, and why does my connection fail on a current runtime".

## Contents

| Page | What it covers |
|---|---|
| [Overview](docs/index.md) | What OpenDXL is and why a fabric instead of point-to-point integrations |
| [Architecture](docs/architecture.md) | Brokers, clients, services, the four message types, deployment topologies |
| [Getting started](docs/getting-started.md) | Broker in Docker to first message, in about ten minutes |
| [Messages and payloads](docs/concepts/messages.md) | The envelope, MessagePack, size limits, error handling |
| [Services and requests](docs/concepts/services.md) | Registration, TTL, load balancing, threading |
| [Topics and authorization](docs/concepts/topics-and-authorization.md) | Naming conventions and the broker's policy model |
| [Python](docs/clients/python.md) · [Java](docs/clients/java.md) · [JavaScript](docs/clients/javascript.md) · [Node-RED](docs/clients/node-red.md) | Per-client usage and pitfalls |
| [The broker](docs/broker/index.md) · [TLS and ciphers](docs/broker/tls.md) | Running a fabric, and the cipher problem that breaks current clients |
| [Integrations](docs/integrations.md) | TIE, ePO, MAR, VirusTotal, MISP and the rest |
| [Repositories](docs/repositories.md) | All 45 repositories, grouped by purpose |
| [Compatibility](docs/compatibility.md) | Version matrix, what is broken, what is fixed where |
| [The maintained fork](docs/fork.md) | Every fix in the fork, per repository, and how to install it |
| [Security](docs/security.md) | Certificates, transport, authorization, payload hygiene |
| [Community](docs/community.md) · [History](docs/history.md) | Where to ask; McAfee to Trellix, stewardship, trademarks |

## Building

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

### A standalone copy

`tools/build_offline.py` produces a folder that works from a local disk - open
`index.html` in a browser, no web server, no network:

```bash
python tools/build_offline.py           # -> site-offline/
python tools/build_offline.py --zip     # also dist/opendxl-docs-offline-<date>.zip
```

It differs from `mkdocs build` in three ways, and each of them is the reason a
plain build does not work from a folder:

* `mkdocs.offline.yml` writes `page.html` instead of `page/index.html` - a
  directory URL needs a server - and turns off the web font, which would be the
  one request that leaves the machine.
* Material's search only works from `file://` through the `iframe-worker` shim,
  which the theme loads from a CDN. The script vendors it into the output and
  caches it under `tools/vendor/`. Without network access the build still
  succeeds and says that search is the one thing that will not work.
* `404.html` is dropped: its links are absolute, because a not-found page is
  served from an arbitrary URL, and from a folder nothing serves it anyway.

Afterwards every internal link is resolved against the output, and a link that
does not resolve fails the build - a copy that looks fine on the first page and
404s two clicks deeper is worse than no copy.

Two pages are generated; edit their data files, not the Markdown:

```bash
python tools/gen_repositories.py   # docs/repositories.md <- data/repositories.json
python tools/gen_fork.py           # docs/fork.md         <- data/fork-changes.json
```

`data/fork-changes.json` is extracted from the git history of the fork clones by a local
script, so the fork page cannot drift from what was actually committed.

## Contributing

See [Contributing](docs/contributing.md). Corrections are the most useful contribution — this
documentation describes code that has moved on since its last release.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

This is a community documentation project. It is not an official Trellix product and is not
endorsed by Musarubra US LLC. Trademarks are covered in [NOTICE](NOTICE).
