// Pyodide bridge — the in-browser twin of server.py's /api/analyze. Boots Pyodide
// once (singleton), unpacks the gaitlab/ engine zip into its virtual FS, and runs the
// unchanged Python analyze() over a pose dict. Marshaling goes through JSON strings to
// sidestep PyProxy edge cases.

import { PYODIDE_INDEX_URL, GAITLAB_ZIP_URL } from "./config.js";

const ENGINE_DIR = "/gaitlab_pkg"; // the zip contains a top-level gaitlab/ dir

let _boot = null;
function boot(onProgress = () => {}) {
  if (_boot) return _boot;
  _boot = (async () => {
    onProgress(0, "Loading Python runtime…");
    const { loadPyodide } = await import(`${PYODIDE_INDEX_URL}pyodide.mjs`);
    const pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX_URL });

    onProgress(0.5, "Loading analysis engine…");
    const buf = await (await fetch(GAITLAB_ZIP_URL)).arrayBuffer();
    pyodide.unpackArchive(buf, "zip", { extractDir: ENGINE_DIR });

    // Bind a JSON-in / JSON-out entry point once; reuse it per analysis.
    const run = pyodide.runPython(`
import sys, json
sys.path.insert(0, ${JSON.stringify(ENGINE_DIR)})
import gaitlab
from gaitlab.core.schema import PoseSequence

def _run(pose_json, label, profile_json):
    pose = json.loads(pose_json)
    profile = json.loads(profile_json) if profile_json else None
    res = gaitlab.analyze(PoseSequence.from_pose_dict(pose), label or "", profile)
    return json.dumps(res.to_dict())

_run
`);
    onProgress(1, "Engine ready");
    return { pyodide, run };
  })();
  return _boot;
}

// Kick off the Pyodide + engine boot early (e.g. when the upload screen mounts) so the
// download overlaps with the user picking a clip. Safe to call repeatedly.
export const preload = (onProgress) => boot(onProgress);

// poseDict -> result dict (the flat AnalysisResult.to_dict()). onProgress(fraction, note).
export async function runAnalysis(poseDict, label, profile, onProgress = () => {}) {
  const { run } = await boot(onProgress);
  onProgress(1, "Analyzing…");
  const out = run(JSON.stringify(poseDict), label || "", profile ? JSON.stringify(profile) : "");
  return JSON.parse(out);
}
