// Conformance harness (ADR-0002 §4, level 1) — the JS side.
//
// Reads a JSON array of {js, signals} on stdin, evaluates each compiled
// rg.forms JS expression against its signals, and writes a JSON array of
// results to stdout. Field references are compiled as `__sig("path")` calls
// (the Python serializer is given a matching signal_ref), so string literals in
// the expression are never mistaken for signal references.
//
// The compiled JS relies only on standard globals (Boolean, Number, typeof,
// isNaN), which is exactly the surface a Datastar expression has.

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", reject);
  });
}

function makeSig(signals) {
  // Resolve a (possibly dotted) signal path; missing -> null (Datastar seeds
  // all signals, and our evaluator defaults a missing reference to null).
  return (path) => {
    let cur = signals;
    for (const part of String(path).split(".")) {
      if (cur == null || !(part in cur)) return null;
      cur = cur[part];
    }
    return cur === undefined ? null : cur;
  };
}

function normalize(value) {
  // Make results comparable to the Python side and JSON-safe.
  if (typeof value === "number" && !Number.isFinite(value)) {
    return { __nonfinite__: String(value) };
  }
  return value;
}

const input = JSON.parse(await readStdin());
const results = input.map(({ js, signals }) => {
  const __sig = makeSig(signals);
  // eslint-disable-next-line no-new-func
  const fn = new Function("__sig", `"use strict"; return (${js});`);
  return normalize(fn(__sig));
});
process.stdout.write(JSON.stringify(results));
