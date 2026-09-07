# Integrations

The reference integrations are the reason most people arrive at OpenDXL: they show what a real
DXL service looks like, and several of them are directly useful.

They come in pairs. A **service** is a process you run; it registers a request topic and
answers on it, normally by calling a third-party API. A **client library** is what a caller
imports so it does not have to build the request payload by hand. You can use a service
without its client library — the contract is just a topic and a payload — but the library is
where the parameter names and result shapes are documented.

```
your code ──> tie_client.get_file_reputation(hashes)          client library
                     │  builds a Request for
                     ▼  /mcafee/service/tie/file/reputation
              [ DXL fabric ]
                     │  routes to a registered instance
                     ▼
              TIE service ──> product / vendor API
```

## Trellix product integrations

These talk to services that are part of a Trellix deployment; the service side already exists
on the fabric and only the client library is an OpenDXL project.

| Product | Client library | What it gives you |
|---|---|---|
| **Threat Intelligence Exchange (TIE)** | `opendxl-tie-client-python`, `opendxl-tie-client-javascript` | File and certificate reputations, set reputations, subscribe to reputation-change events |
| **ePolicy Orchestrator (ePO)** | `opendxl-epo-client-python`, `opendxl-epo-client-javascript` | Run any ePO remote command over DXL — tags, system tree, queries |
| **Active Response (MAR)** | `opendxl-mar-client-python`, `opendxl-mar-client-javascript` | Real-time searches across endpoints |

TIE is the one worth understanding as a design example. Reputation *lookups* are requests —
one caller, one answer. Reputation *changes* are events on `/mcafee/event/tie/file/repchange`,
so any number of consumers can react to a conviction without TIE knowing they exist. That
split is the whole event/request distinction in one product.

## Third-party service integrations

Each of these is a service you run yourself, and most have a matching client library.

| Service | Repository | Wraps |
|---|---|---|
| VirusTotal | `opendxl-virustotal-service-python` | File/URL/domain/IP reports |
| MISP | `opendxl-misp-service-python` | MISP REST API — events, attributes, search |
| MaxMind | `opendxl-maxmind-service-python` | GeoIP host/IP geolocation |
| DomainTools | `opendxl-domaintools-service-python` | Whois, reverse DNS, reputation |
| Elasticsearch | `opendxl-elasticsearch-service-python` | Index and query documents from the fabric |
| URLVoid | `opendxl-urlvoid-service-python` | URL reputation |
| TheHive | `opendxl-thehive-service-python` | Case and alert creation |

The pattern is identical across all of them, which is what makes them good templates: a
configuration file with the API credentials, a `dxlbootstrap`-generated service skeleton, one
request callback per API operation, and a JSON payload contract.

Most need an API key for the wrapped service, supplied in the service configuration file — not
on the fabric. Do not put third-party credentials in DXL payloads.

## Other integrations

- **Cisco pxGrid** (`opendxl-pxgrid-client-python`) — bridges Cisco's ISE grid to DXL.
  See the note about pxGrid 2.0 in [Compatibility](compatibility.md#open-items).
- **OpenC2** (`opendxl-openc2-client-python`) — sends OASIS OpenC2 commands over DXL.
- **Cuckoo Sandbox** (`opendxl-cuckoo-reporting-module`) — a Cuckoo reporting module that
  publishes analysis results onto the fabric as events.
- **SIEM** (`opendxl-siem-sensor`, Rust) — the other direction: the fabric's own events, normalised
  to OCSF/CEF and forwarded to a SIEM, with detections. See [SIEM sensor](siem-sensor.md).

## Running a service

All the Python services follow the same shape:

```bash
git clone https://github.com/opendxl/opendxl-virustotal-service-python
cd opendxl-virustotal-service-python
pip install .

# config/dxlvtapiservice.config — API key and service settings
# config/dxlclient.config       — from provisioning
python -m dxlvtapiservice config
```

The service connects, registers its topics, and stays up. Read
[Services and requests](concepts/services.md) for what registration, TTL and load balancing
mean when you run more than one instance.

!!! warning "Check the dependency state first"
    The published services still pull `dxlclient` with its `msgpack<1.0.0` pin, and
    `dxlbootstrap` 0.2.2 breaks on setuptools ≥ 82. See
    [Compatibility](compatibility.md) before deploying one as it is.

## Writing your own

Use [`opendxl-bootstrap-python`](repositories.md#tooling-and-scaffolding) — it generates the
service skeleton, configuration handling, logging and the registration lifecycle, so what you
write is the request callbacks. The design questions worth settling before you start are in
[Services and requests](concepts/services.md#writing-a-service-that-other-people-can-use).
