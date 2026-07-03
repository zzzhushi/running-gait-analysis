// Layer 2 — Pyodide == Python parity. Boots the SAME gaitlab engine inside Pyodide
// (node build), runs each committed input pose through it, and deep-equals the result
// against the Python-produced result.json. This is what proves the WASM path is faithful;
// the JS side never re-implements the math.
//
//   python3 scripts/build_web.py && node web/tests/parity.mjs
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadPyodide } from "pyodide";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIX = path.join(HERE, "fixtures");
const ZIP = path.join(HERE, "..", "py", "gaitlab.zip");
const TOL = 1e-6;

// First numeric/structural mismatch as a path string, or null if equal within tol.
function deepDiff(a, b, at = "$") {
  if (typeof a === "number" && typeof b === "number") {
    if (Number.isNaN(a) && Number.isNaN(b)) return null;
    return Math.abs(a - b) <= TOL ? null : `${at}: ${a} != ${b}`;
  }
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b)) return `${at}: array/non-array`;
    if (a.length !== b.length) return `${at}: length ${a.length} != ${b.length}`;
    for (let i = 0; i < a.length; i++) {
      const d = deepDiff(a[i], b[i], `${at}[${i}]`);
      if (d) return d;
    }
    return null;
  }
  if (a && b && typeof a === "object" && typeof b === "object") {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) {
      const d = deepDiff(a[k], b[k], `${at}.${k}`);
      if (d) return d;
    }
    return null;
  }
  return a === b ? null : `${at}: ${JSON.stringify(a)} != ${JSON.stringify(b)}`;
}

const RUN_PY = `
import sys, json
sys.path.insert(0, "/gaitlab_pkg")
import gaitlab
from gaitlab.core.schema import PoseSequence

def _run(pose_json, label, profile_json):
    pose = json.loads(pose_json)
    profile = json.loads(profile_json) if profile_json else None
    res = gaitlab.analyze(PoseSequence.from_pose_dict(pose), label or "", profile)
    return json.dumps(res.to_dict())

_run
`;

async function main() {
  const pyodide = await loadPyodide();
  const zip = await readFile(ZIP);
  pyodide.unpackArchive(new Uint8Array(zip), "zip", { extractDir: "/gaitlab_pkg" });
  const run = pyodide.runPython(RUN_PY);

  const names = (await readdir(FIX))
    .filter((f) => f.endsWith(".input.json"))
    .map((f) => f.slice(0, -".input.json".length));
  if (!names.length) throw new Error("no fixtures — run scripts/gen_web_fixtures.py");

  let failures = 0;
  for (const name of names.sort()) {
    const pose = JSON.parse(await readFile(path.join(FIX, `${name}.input.json`), "utf8"));
    const expected = JSON.parse(await readFile(path.join(FIX, `${name}.result.json`), "utf8"));
    const label = expected.summary?.label || "";
    const profile = expected.summary?.profile || null;
    const got = JSON.parse(run(JSON.stringify(pose), label, profile ? JSON.stringify(profile) : ""));
    const diff = deepDiff(expected, got);
    if (diff) { console.error(`✗ ${name}  ${diff}`); failures++; }
    else console.log(`✓ ${name}`);
  }
  console.log(failures ? `\n${failures} fixture(s) diverged` : `\nparity ok (${names.length} fixtures)`);
  process.exit(failures ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
