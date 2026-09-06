# Node-RED nodes

`@opendxl/node-red-contrib-dxl` puts the fabric into [Node-RED](https://nodered.org/) as flow
nodes: connect once in a configuration node, then drag event and request nodes into a flow. It
is the fastest way to prototype an integration, and a reasonable way to run small ones.

- Upstream: [opendxl/node-red-contrib-dxl](https://github.com/opendxl/node-red-contrib-dxl)

## Install

From the Node-RED palette manager, or:

```bash
cd ~/.node-red
npm install @opendxl/node-red-contrib-dxl
```

A ready-made container with Node-RED and the DXL nodes already installed is available as
[opendxl-node-red-docker](../repositories.md#containers-and-environments).

## Nodes

| Node | Kind | Purpose |
|---|---|---|
| `dxl-client` | config | Holds the path to `dxlclient.config`; shared by every other node |
| `dxl-event in` | input | Subscribes to a topic; each event starts a flow with the payload in `msg.payload` |
| `dxl-event out` | output | Publishes `msg.payload` as an event |
| `dxl-request` | function | Sends a request and passes the response on |
| `dxl-response` | output | Replies to a request received by a service node |
| `dxl-service` | input | Registers a service topic; incoming requests start the flow |

## Product-specific node packages

Each wraps a service so a flow does not have to build request payloads by hand:

- `@opendxl/node-red-contrib-dxl-epo-client` — run ePO commands
- `@opendxl/node-red-contrib-dxl-tie-client` — file and certificate reputations
- `@opendxl/node-red-contrib-dxl-mar-client` — Active Response searches
- `@opendxl/node-red-contrib-dxl-pxgrid-client` — Cisco pxGrid

They all depend on `@opendxl/dxl-client`, so the dependency note in
[JavaScript client](javascript.md#dependency-state) applies to them too.

## Practical notes

- **The config node holds a real identity.** `dxlclient.config` and its key give the flow the
  full rights of that certificate on the fabric. Exporting a flow that points at them is not
  harmless just because the files themselves are not in the export.
- **A `dxl-event in` node on a broad wildcard will flood the flow.** Node-RED processes
  messages one at a time per node; a busy topic backs a flow up indefinitely. Filter at the
  topic, not in a downstream function node.
- **Choose the request timeout deliberately.** For interactive flows, set it low enough that a
  dead service does not stall the flow behind it.
