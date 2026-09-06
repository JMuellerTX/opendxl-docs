# Contributing

This repository holds the OpenDXL documentation — the prose, not the client libraries. Code
changes belong in the repository they affect; see [Repositories](repositories.md).

## What is useful here

- **Corrections.** A wrong default, a dead link, an API that no longer looks like the example.
  These are the highest-value contributions because the documentation covers code that moves
  faster than it does.
- **Gaps.** A step that assumes knowledge the reader does not have; an error message with no
  entry in [Compatibility](compatibility.md) or [TLS](broker/tls.md).
- **Field experience.** A broker version, runtime version or fabric configuration that behaves
  differently from what is written here. Say what you ran and what happened.

## What does not belong

- Marketing copy. This is reference documentation for people building something.
- Tutorials for third-party products that only mention DXL in passing.
- Copies of upstream API documentation. Link to it instead — the generated pydoc, javadoc and
  jsdoc are authoritative and stay in sync with their code.

## How to write

- **Concrete over general.** A default value, a command that runs, an error string someone can
  search for. "Configure TLS appropriately" helps nobody.
- **Say what breaks.** Most of the durable value in this documentation is in the failure modes,
  not the happy paths — the happy paths are in the READMEs already.
- **British or American spelling, consistently within a page.** No preference between them.
- **Wrap prose at 92 characters** to keep diffs readable.
- **Every claim about behaviour should be checkable.** If you state a default, name the setting
  it comes from. If you describe a failure, describe how to reproduce it.

## Structure

```
docs/
  index.md                 what OpenDXL is
  architecture.md          the fabric model
  getting-started.md       broker to first message
  concepts/                messages, services, topics and authorization
  clients/                 python, java, javascript, node-red
  broker/                  running a broker, TLS and ciphers
  integrations.md          the reference services and their client libraries
  repositories.md          generated — see below
  compatibility.md         versions, TLS matrix, what is broken and what is fixed
  fork.md                  generated — every change in the maintained fork
  security.md              hardening guidance
  community.md             where to ask
  history.md               McAfee to Trellix, stewardship, trademarks
data/repositories.json     source of truth for the repository catalogue
data/fork-changes.json     the fork's commits, extracted from git history
tools/gen_repositories.py  regenerates docs/repositories.md
tools/gen_fork.py          regenerates docs/fork.md
```

`docs/repositories.md` and `docs/fork.md` are **generated**. Edit the JSON and run the
matching tool:

```bash
python tools/gen_repositories.py
python tools/gen_fork.py
```

`data/repositories.json` also feeds the repository listing on the community site, so a change
there shows up in both places. `data/fork-changes.json` is produced from the git history of
the fork clones by a local script — do not hand-edit it; re-extract instead, so the page
cannot claim a fix that was never committed.

## Building the site

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

## Licensing of contributions

This repository is Apache-2.0. By contributing you agree that your contribution is licensed
under the same terms. Retain existing copyright notices; do not rewrite the McAfee LLC
notices in quoted code (see [history](history.md#what-mcafee-in-the-code-means)).
