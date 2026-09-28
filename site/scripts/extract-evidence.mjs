// Builds src/data/evidence.json from committed run artifacts in the repository.
// Every number the site displays is read here from a file under docs/evidence,
// STATE.md or tests/golden. Nothing is typed in by hand. Run: npm run evidence
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..");
const read = (p) => JSON.parse(readFileSync(join(repo, p), "utf8"));
const fail = (msg) => {
  throw new Error(`evidence extraction: ${msg}`);
};

// M1 sensitivity study: exact-moment z-scores for every printed value.
const sensPath = "docs/evidence/m1-sensitivity/run/sensitivity.json";
const sens = read(sensPath);
const sensManifest = read("docs/evidence/m1-sensitivity/run/manifest.json");
if (sensManifest.git_dirty !== false || sensManifest.status !== "completed") {
  fail("M1 sensitivity run is not a clean completed run");
}
const METRIC_LABEL = {
  profit_mean: "Profit mean",
  profit_std: "Profit SD",
  final_q_mean: "Final inventory mean",
  final_q_std: "Final inventory SD",
};
const runs = sens.results.map((r) => {
  const tests = [];
  for (const t of r.tables) {
    for (const strategy of ["inventory", "symmetric"]) {
      const cell = t[strategy];
      if (cell.status !== "completed") {
        tests.push({ table: t.table, gamma: t.gamma, strategy, metric: "all", status: "undefined" });
        continue;
      }
      for (const [metric, v] of Object.entries(cell.tests)) {
        tests.push({
          table: t.table,
          gamma: t.gamma,
          strategy,
          metric,
          label: METRIC_LABEL[metric],
          paper: v.paper,
          population: v.population,
          z: v.z,
          status: "tested",
        });
      }
    }
    if (t.variance_ratio) {
      const v = t.variance_ratio;
      tests.push({
        table: t.table,
        gamma: t.gamma,
        strategy: "both",
        metric: "variance_ratio",
        label: "Variance ratio",
        paper: v.paper,
        population: v.population,
        z: v.z,
        relative_deviation: v.relative_deviation,
        se_log: v.se_log,
        status: "tested",
      });
    }
  }
  return {
    rule: r.rule,
    dt: r.dt,
    tests_run: r.tests_run,
    failures: r.failures,
    max_abs_z: r.max_abs_z,
    consistent: r.consistent,
    acceptance_candidate: r.acceptance_candidate,
    invalid: r.invalid,
    tests,
  };
});

// The original seeded contract: raw fill probabilities above one.
const comparison = read("docs/evidence/m1-qf2008/run/comparison.json");
const overflow = comparison.experiments
  .filter((e) => e.variant === "published_saturated")
  .map((e) => ({
    table: e.table,
    gamma: e.gamma,
    max_raw_probability: e.inventory.max_raw_probability,
    exceedances: e.inventory.probability_exceedances,
  }));
const strictInvalid = comparison.experiments
  .filter((e) => e.variant === "published_strict" && e.inventory.status === "invalid_probability")
  .map((e) => e.table);

// Published table and parameters (the human-owned golden file).
const golden = read("tests/golden/as2008_table_qf2008.json");
const params = golden.simulation_params;

// M0: real LOBSTER ingestion validation.
const m0dir = "docs/evidence/m0-normalization";
const m0 = readdirSync(join(repo, m0dir))
  .filter((f) => f.endsWith("-manifest.json"))
  .sort()
  .map((f) => {
    const m = read(join(m0dir, f));
    if (m.status !== "passed") fail(`${f} did not pass`);
    return { symbol: f.replace("-manifest.json", ""), events: m.n_events, commit: m.git_sha.slice(0, 7) };
  });

// M3 fixture: only pipeline facts, never economic values.
const folds = read("docs/evidence/m3-fixture/run/pco_folds.json");
const m3Manifest = read("docs/evidence/m3-fixture/run/manifest.json");
const attribution = read("docs/evidence/m3-fixture/run/attribution.json");
const symbols = Object.keys(
  attribution.strategies.avellaneda_stoikov.by_cancel_policy.uniform.per_symbol,
);

// Engineering gate as recorded in STATE.md.
const state = readFileSync(join(repo, "STATE.md"), "utf8");
const passed = state.match(/pytest: (\d+) passed, 0 failed/);
if (!passed) fail("STATE.md does not record a clean pytest result");

const evidence = {
  generated_from_commit: sensManifest.git_sha.slice(0, 7),
  m1: {
    source: sensPath,
    commit: sensManifest.git_sha.slice(0, 7),
    elapsed_seconds: sensManifest.elapsed_seconds,
    threshold: sens.threshold_abs_z,
    family_size: sens.family_size,
    paper_n: params.n_simulations,
    consistent_at_paper_dt: sens.consistent_rules_at_paper_dt,
    runs,
    overflow,
    strict_invalid_tables: strictInvalid,
    params: { s0: params.s0, T: params.T, sigma: params.sigma, dt: params.dt, k: params.k, A: params.A },
    gammas: golden.tables.map((t) => t.gamma),
  },
  m0: { samples: m0, total_events: m0.reduce((a, b) => a + b.events, 0) },
  m3_fixture: {
    source: "docs/evidence/m3-fixture/run",
    commit: m3Manifest.git_sha.slice(0, 7),
    folds: folds.length,
    converged: folds.filter((f) => f.converged).length,
    symbols: symbols.length,
    episodes: attribution.strategies.avellaneda_stoikov.by_cancel_policy.uniform.n_episodes,
    a3_sign_flips: attribution.strategies.avellaneda_stoikov.bounds.A3.sign_flips_across_bounds,
    budget: m3Manifest.config.strategies.budget,
  },
  gate: { tests_passed: Number(passed[1]) },
};

writeFileSync(join(here, "..", "src", "data", "evidence.json"), JSON.stringify(evidence, null, 2) + "\n");
console.log(
  `evidence.json written: ${runs.length} M1 runs, ${m0.length} M0 samples, ${folds.length} fixture folds`,
);
