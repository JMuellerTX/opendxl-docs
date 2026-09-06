# JavaScript client (Node.js)

Package `@opendxl/dxl-client`. Node.js only — it needs TLS sockets and the filesystem, so it
does not run in a browser.

- Upstream: [opendxl/opendxl-client-javascript](https://github.com/opendxl/opendxl-client-javascript)
- API documentation: [opendxl.github.io/opendxl-client-javascript](https://opendxl.github.io/opendxl-client-javascript/jsdoc/)

## Install

```bash
npm install @opendxl/dxl-client
```

## Connect

```js
const dxl = require('@opendxl/dxl-client')

const config = dxl.Config.createDxlConfigFromFile('./config/dxlclient.config')
const client = new dxl.Client(config)

client.connect(function () {
  // connected
})
```

The JavaScript client is **callback-based throughout** — there is no promise API upstream.
Wrap the calls yourself if you want `async`/`await`:

```js
const { promisify } = require('util')
const connect = promisify(client.connect).bind(client)
await connect()
```

## Events

```js
client.addEventCallback('/isv/acme/event/verdict', function (event) {
  console.log(event.payload.toString())
})

const event = new dxl.Event('/isv/acme/event/verdict')
event.payload = JSON.stringify({ verdict: 'malicious' })
client.sendEvent(event)
```

## Requests

```js
const request = new dxl.Request('/isv/acme/service/sandbox/detonate')
request.payload = JSON.stringify({ sha256: '...' })

client.asyncRequest(request, function (error, response) {
  if (error) {
    if (error instanceof dxl.MessageError) {
      console.error(error.dxlErrorResponse.errorMessage)
    }
    return
  }
  console.log(response.payload.toString())
})
```

Unlike the Python and Java clients, the JavaScript client surfaces a service-side error as an
**error argument** rather than as a response you have to inspect. It is the one place where
this client is harder to get wrong than the others.

## Services

```js
const info = new dxl.ServiceRegistrationInfo(client, '/isv/acme/service/sandbox')
info.addTopic('/isv/acme/service/sandbox/detonate', function (request) {
  const response = new dxl.Response(request)
  response.payload = result
  client.sendResponse(response)
})
client.registerServiceAsync(info)
```

## Dependency state

The published `@opendxl/dxl-client@0.1.4` (2020) pulls `mqtt` 2.x, which brings `ws` 6.2.1 and
a set of known advisories, plus `tmp` 0.0.33. The modernized fork moves to `mqtt` 5.x and
current `tmp`/`uuid`.

This matters beyond the client itself: every downstream package — `@opendxl/dxl-bootstrap`,
the `node-red-contrib-dxl-*` nodes, and the ePO/TIE/MAR JavaScript client libraries — depends
on the **published** `0.1.4`, so their dependency trees keep the old versions until a release
of the fixed client reaches npm. See [Compatibility](../compatibility.md).
