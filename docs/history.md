# Project history and stewardship

## Timeline

| When | What |
|---|---|
| 2015 | Data Exchange Layer ships as a McAfee product feature — a messaging fabric used by McAfee products and, later, by Security Innovation Alliance partners. |
| 2016 | **OpenDXL** opens the fabric to everyone: Apache-2.0 client libraries, an open source broker, and documentation, so an integration no longer needs a partner agreement. |
| 2017–2019 | The ecosystem fills in — Java and JavaScript clients, Node-RED nodes, the bootstrap generator, the console, and the third-party service integrations. |
| Oct 2019 | OpenDXL joins the [Open Cybersecurity Alliance](https://opencybersecurityalliance.org/) (OCA) as a founding contribution. |
| 2019–2021 | Upstream commit activity tapers off. The last releases of most repositories date from this window. |
| Jan 2022 | McAfee Enterprise and FireEye combine and rebrand as **Trellix**. The legal entity behind the products is **Musarubra US LLC**. |
| 2024 | Several OpenDXL repositories receive a copyright and link refresh upstream — `Copyright 2024 Musarubra US LLC`, links pointing at trellix.com — without functional changes. |
| Today | The protocol is unchanged and DXL is a shipping Trellix capability. The core clients still get occasional releases; the integration repositories have been dormant since 2019-2021. See [Compatibility](compatibility.md). |

## What "McAfee" in the code means

Names appear in three places, and they mean different things:

**Copyright headers.** Most source files carry `Copyright (c) 2018 McAfee LLC`. Under the
Apache License 2.0 these notices must be **retained** — §4(a) and §4(b) require preserving
the copyright, patent, trademark and attribution notices in any redistribution. They are a
record of who wrote the code in 2018, not a statement about who owns the company today, and
rewriting them is not a rebranding task. Repositories touched upstream in 2024 carry
`Copyright 2024 Musarubra US LLC` for the newer work; both forms are correct for their
respective contributions.

**Topic names.** The `/mcafee/…` namespace is part of the wire protocol —
`/mcafee/service/dxl/svcregistry/register`, `/mcafee/service/tie/file/reputation`. Renaming
these would break every deployed client and every broker policy. They stay.

**Product names in prose.** McAfee ePolicy Orchestrator is now Trellix ePolicy Orchestrator,
McAfee Threat Intelligence Exchange is Trellix Threat Intelligence Exchange, and McAfee Active
Response is Trellix Active Response. This documentation uses the current names, and notes the
old ones where you will still meet them in a topic string or a class name.

## What stewardship looks like now

OpenDXL is Apache-2.0 code with an open history and no active upstream maintainer. Being
honest about that is more useful than a status badge:

- **The protocol is stable and supported.** DXL is a shipping Trellix capability with its own
  release train. A client written against the fabric today keeps working.
- **The open source packages are not maintained upstream.** No releases since 2020/2021, and
  the accumulated dependency drift described in [Compatibility](compatibility.md) is real.
- **The license does not expire.** Apache-2.0 is irrevocable. Anyone may fork, fix and
  redistribute, and several people have. The fork this documentation is written against is
  maintained by [@JMuellerTX](https://github.com/JMuellerTX) and covers all 45 repositories —
  see [the maintained fork](fork.md).

If you are choosing DXL for a new integration: the fabric is a reasonable choice, and you
should expect to carry the client library yourself — pin a fork, or vendor it, rather than
depending on a release cadence that does not exist.

## Trademarks

The Apache License grants copyright and patent rights. It explicitly does **not** grant
trademark rights (§6). Trellix, the Trellix logo, Musarubra and the product names are
trademarks of Musarubra US LLC. Using the code is a licensing matter; using the marks is a
separate permission.

## Where the conversation moved

The forum that used to live on opendxl.com is closed. Discussion happens in the
[Trellix Community](community.md) and in the GitHub issue trackers of the individual
repositories.
