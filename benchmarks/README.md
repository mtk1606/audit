# AS benchmark

Submit a strategy by writing a factory `make(tick: int) -> Quoter`, where
`Quoter` is the protocol in `src/asaudit/strategy/base.py`. The benchmark runs
it on every policy-fit episode, in all eight ablation cells and under all three
cancel-attribution policies, with the same seeds as the published AS and
symmetric baselines. It reports mean P&L and P&L per notional (bps), each with a
stationary block bootstrap CI, beside those baselines.

```bash
uv run asaudit benchmark --quoter benchmarks.example_quoter:make \
    --config configs/ablation/lobster.toml
```

Use `configs/ablation/fixture.toml` to try it without market data. Fixture
numbers are synthetic and are labelled as such.
