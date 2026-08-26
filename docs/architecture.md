# Architecture

GaitLab has one browser interface and one portable analysis engine, but two runtime
paths. The boundary between them is deliberate: `gaitlab/` is the engine that can run
unchanged in CPython or Pyodide, while `gaitlab_local/` contains the application code
that only makes sense on a local machine.

## Package responsibilities

| Path | Responsibility | Runtime dependencies |
|---|---|---|
| `gaitlab/` | Pose schema, gait events, metrics, scoring, and coaching | Python standard library only |
| `gaitlab_local/` | Local use cases, SQLite persistence, pose caching, video ingestion, and HTTP routes | `gaitlab/` and the Python standard library |
| `extractor/` | Optional RTMPose or MediaPipe video-to-pose adapters | OpenCV plus the selected pose backend |
| `web/` | The shared single-page interface and browser pose extraction | Browser APIs; Pyodide and MediaPipe in the static runtime |
| `server.py` | Local CLI and composition root | `gaitlab_local/` |

`gaitlab_local/` is a sibling of `gaitlab/`, not a subpackage of it. The Pages build
recursively zips `gaitlab/` into `web/py/gaitlab.zip`. Keeping the local application
outside that tree makes the deployment boundary structural: SQLite, filesystem,
subprocess, and HTTP modules cannot be pulled into the Pyodide bundle simply because a
new local module was added. Dependencies point inward—`gaitlab_local` may use
`gaitlab`, but the portable engine must never import the local application.

The local package is split by responsibility:

- `repository.py` owns the SQLite schema and user/run persistence.
- `cache.py` owns validated pose-cache paths and atomic cache promotion.
- `ingest.py` owns the video catalog and invokes an extractor subprocess when a pose
  is not already cached.
- `application.py` coordinates analysis, seeding, ingestion, and optional narratives.
- `http.py` maps HTTP requests to those application operations and serves the SPA.

`server.py` only parses command-line options, wires these pieces together, and starts
the server. The extractor remains a separate process boundary so its optional model
dependencies are not imported by the server or analysis engine.

## GitHub Pages runtime

```text
local video selected in the browser
  -> MediaPipe Tasks Vision creates the canonical pose sequence
  -> web/js/runtime/static.js accepts the analyze operation
  -> web/js/engine.js starts Pyodide
  -> Pyodide loads web/py/gaitlab.zip
  -> gaitlab.analyze(...) returns the report
  -> the static runtime keeps the result in memory for the current page session
```

There is no Python server, SQLite database, filesystem pose cache, or extractor
subprocess in this path. The video and pose analysis remain in the browser, and report
history disappears when the page is refreshed.

`scripts/build_web.py` is the deployment boundary. It packages Python files from
`gaitlab/` only, then the Pages workflow publishes `web/`. Pyodide, MediaPipe Tasks
Vision, and the pose model are pinned browser-time dependencies; `gaitlab_local/` and
the local extractor dependencies are not part of the Pages artifact.

## Local server runtime

```text
web SPA (?runtime=server selects web/js/runtime/server.js)
  -> JSON request handled by gaitlab_local.http
  -> gaitlab_local.application coordinates the use case
     -> gaitlab_local.ingest resolves a video and, when needed, runs extractor/
     -> gaitlab analyzes the canonical pose sequence
     -> gaitlab_local.repository stores the report in SQLite
  -> JSON response returned to the same SPA
```

The local server adds durable users, run history, trends, comparisons, cached pose
files, and optional local narratives. The server and engine themselves remain
standard-library Python. Extracting a new real video requires the optional packages in
`requirements.txt`; cached poses and synthetic demo runs do not.

`web/js/api.js` is the stable UI-facing facade. Each adapter publishes explicit
capabilities, so screens can hide server-only history, users, disk ingestion, seeding,
and narratives in the static runtime instead of discovering the boundary through
failed requests.

## Boundary rules

- `gaitlab/` must not import `gaitlab_local`, `server.py`, `extractor/`, or web code.
- `gaitlab_local/` may depend on `gaitlab`, but engine code must not know how results
  are stored or served.
- Heavy pose dependencies stay behind the extractor entry points and are loaded only
  when extraction is requested.
- Both runtimes consume the same canonical pose schema and execute the same
  `gaitlab.analyze` implementation.
- Changes to engine numbers must keep the Python/Pyodide parity suite green.
- A static build must contain `gaitlab/...` Python modules and no
  `gaitlab_local/...` modules.

## Build and verification

```bash
pytest              # Python engine and local-application tests
make web-static     # build web/py/gaitlab.zip from gaitlab/ only
make test-web       # browser mapping tests plus Pyodide/Python parity
make serve-static   # serve the same static shape deployed to Pages
```

The product therefore has two application runtimes, not two analysis engines. That is
the central constraint: local-only capabilities may grow without forking the numerical
engine or widening the GitHub Pages dependency surface.
