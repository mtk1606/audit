// Every quantitative claim on the page, computed from evidence.json.
// index.html carries each value as static text inside <span data-ev="key">;
// scripts/check-claims.mjs fails the build if any static text differs from the
// value computed here, and main.ts re-renders them at runtime from the same map.

const int = new Intl.NumberFormat("en-US");
const fix = (x, d) => Number(x).toFixed(d);

/** @param {any} ev evidence.json */
export function claims(ev) {
  const run = (rule, dt) => {
    const r = ev.m1.runs.find((x) => x.rule === rule && x.dt === dt);
    if (!r) throw new Error(`missing M1 run ${rule} ${dt}`);
    return r;
  };
  const capped = run("saturate", 0.005);
  const poisson = run("poisson", 0.005);
  const c0025 = run("saturate", 0.0025);
  const c001 = run("saturate", 0.001);
  const t1ratio = capped.tests.find((t) => t.table === 1 && t.metric === "variance_ratio");
  const t3 = ev.m1.overflow.find((o) => o.table === 3);
  const t1 = ev.m1.overflow.find((o) => o.table === 1);
  const invCapped = (table) =>
    capped.tests.find((t) => t.table === table && t.strategy === "inventory" && t.metric === "profit_mean");
  const invPoisson = (table) =>
    poisson.tests.find((t) => t.table === table && t.strategy === "inventory" && t.metric === "profit_mean");
  const drop = (1 - invPoisson(1).population / invCapped(1).population) * 100;
  return {
    "m0.events": int.format(ev.m0.total_events),
    "m0.symbols": String(ev.m0.samples.length),
    "m1.tests": String(capped.tests_run),
    "m1.family": String(ev.m1.family_size),
    "m1.threshold": fix(ev.m1.threshold, 2),
    "m1.capped.max": fix(capped.max_abs_z, 2),
    "m1.capped.fail": String(capped.failures),
    "m1.poisson.fail": String(poisson.failures),
    "m1.poisson.max": fix(poisson.max_abs_z, 1),
    "m1.poisson.t1drop": fix(drop, 0),
    "m1.dt0025.fail": String(c0025.failures),
    "m1.dt001.fail": String(c001.failures),
    "m1.paper_n": int.format(ev.m1.paper_n),
    "m1.t3.maxraw": fix(t3.max_raw_probability, 2),
    "m1.t3.exceed": int.format(t3.exceedances),
    "m1.t1.maxraw": fix(t1.max_raw_probability, 2),
    "m1.t1.ratio.dev": fix(t1ratio.relative_deviation * 100, 1),
    "m1.t1.ratio.z": fix(Math.abs(t1ratio.z), 2),
    "m1.t1.ratio.paper": fix(t1ratio.paper, 2),
    "m1.t1.ratio.pop": fix(t1ratio.population, 2),
    "m1.commit": ev.m1.commit,
    "m1.strict.invalid": ev.m1.strict_invalid_tables.join(" and "),
    "gate.tests": String(ev.gate.tests_passed),
    "fixture.folds": String(ev.m3_fixture.folds),
    "fixture.converged": String(ev.m3_fixture.converged),
    "fixture.budget": String(ev.m3_fixture.budget),
    "fixture.symbols": String(ev.m3_fixture.symbols),
    "fixture.episodes": String(ev.m3_fixture.episodes),
    "fixture.commit": ev.m3_fixture.commit,
  };
}
