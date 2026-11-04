"""Config loading + validation against METHODOLOGY.md contracts (§3, §4, §9, §10).

Every check here is a methodology guarantee; tests/test_weights.py pins the
actual v2.0.0 numbers.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
DEMO_DIR = ROOT / "demo"

NORMALIZATION_MODES = {"blend", "borda_only", "minmax_only", "elo", "log_share"}
KINDS_WITH_ADAPTERS = {"lm_arena", "openrouter", "json_url", "llmstat"}


class ConfigError(ValueError):
    pass


class Config:
    def __init__(self, weights: dict, sources: dict):
        self.weights = weights
        self.sources = sources
        self._validate()

    # -- convenience accessors ------------------------------------------------
    @property
    def version(self) -> str:
        return self.weights["version"]

    @property
    def pillars(self) -> dict:
        return self.weights["pillars"]

    @property
    def pillar_weights(self) -> dict:
        return {pid: p["weight"] for pid, p in self.pillars.items()}

    @property
    def benchmarks(self) -> dict:
        return self.weights["benchmarks"]

    def bench_ids(self) -> list:
        return list(self.benchmarks)

    def bench_weight(self, bench_id: str) -> float:
        return float(self.benchmarks[bench_id]["weight"])

    def bench_pillar(self, bench_id: str) -> str:
        return self.benchmarks[bench_id]["pillar"]

    def bench_norm_mode(self, bench_id: str) -> str:
        return self.benchmarks[bench_id]["normalization"]

    def bench_noise_raw(self, bench_id: str) -> float:
        b = self.benchmarks[bench_id]
        return float(b.get("noise_raw", self.weights["uncertainty"]["default_noise_raw"]))

    def bench_higher_better(self, bench_id: str) -> bool:
        return bool(self.benchmarks[bench_id].get("higher_better", True))

    def alias_source(self, bench_id: str) -> str | None:
        return self.benchmarks[bench_id].get("alias_of")

    @property
    def aggregation(self) -> dict:
        return self.weights["aggregation"]

    @property
    def uncertainty(self) -> dict:
        return self.weights["uncertainty"]

    @property
    def tiers_cfg(self) -> dict:
        return self.weights["tiers"]

    def config_hash(self) -> str:
        payload = json.dumps(
            {"weights": self.weights, "sources": self.sources,
             "model_aliases": yaml.safe_load((CONFIG_DIR / "models.yaml").read_text())},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()[:16]

    # -- validation ------------------------------------------------------------
    def _validate(self) -> None:
        w = self.weights

        for key in ("version", "aggregation", "uncertainty", "tiers", "pillars", "benchmarks"):
            if key not in w:
                raise ConfigError(f"weights.yaml missing top-level key: {key}")

        # §3 pillar weights sum to 1
        psum = sum(p["weight"] for p in w["pillars"].values())
        if abs(psum - 1.0) > 1e-6:
            raise ConfigError(f"pillar weights sum to {psum}, expected 1.0")

        # §4 benchmark weights sum to 1
        bsum = sum(b["weight"] for b in w["benchmarks"].values())
        if abs(bsum - 1.0) > 1e-6:
            raise ConfigError(f"benchmark weights sum to {bsum}, expected 1.0")

        # §4 per-pillar consistency: benchmark weights in each pillar == pillar weight
        for pid, p in w["pillars"].items():
            in_pillar = sum(
                b["weight"] for b in w["benchmarks"].values() if b["pillar"] == pid
            )
            if abs(in_pillar - p["weight"]) > 1e-6:
                raise ConfigError(
                    f"pillar {pid}: benchmark weights sum to {in_pillar} but pillar weight is {p['weight']}"
                )

        for bid, b in w["benchmarks"].items():
            if b["pillar"] not in w["pillars"]:
                raise ConfigError(f"benchmark {bid}: unknown pillar {b['pillar']}")
            if b["normalization"] not in NORMALIZATION_MODES:
                raise ConfigError(
                    f"benchmark {bid}: normalization must be one of {sorted(NORMALIZATION_MODES)}"
                )
            if not (0 < b["weight"] <= 1):
                raise ConfigError(f"benchmark {bid}: weight out of range")
            alias = b.get("alias_of")
            if alias is not None:
                if alias not in w["benchmarks"]:
                    raise ConfigError(f"benchmark {bid}: alias_of {alias} not registered")
                if alias == bid or w["benchmarks"][alias].get("alias_of"):
                    raise ConfigError(f"benchmark {bid}: alias chains/cycles are not allowed")
                if b["normalization"] != w["benchmarks"][alias]["normalization"]:
                    raise ConfigError(f"benchmark {bid}: alias normalization differs")

        # §9 base + span == 1 (full coverage => multiplier exactly 1.0)
        cp = w["aggregation"]["coverage_penalty"]
        if abs(cp["base"] + cp["span"] - 1.0) > 1e-9:
            raise ConfigError("coverage_penalty base + span must equal 1.0")
        if not (0 < cp["base"] < 1):
            raise ConfigError("coverage_penalty base must be in (0,1)")

        # §5 eligibility sanity
        el = w["aggregation"]["eligibility"]
        if not (1 <= el["min_pillars"] <= len(w["pillars"])):
            raise ConfigError("eligibility.min_pillars out of range")
        if not (1 <= el["min_benchmarks"] <= len(w["benchmarks"])):
            raise ConfigError("eligibility.min_benchmarks out of range")

        # §10 bootstrap sanity
        u = w["uncertainty"]
        if int(u["bootstrap_reps"]) < 100:
            raise ConfigError("bootstrap_reps must be >= 100")
        if not (0.5 < u["dominance_threshold"] < 1.0):
            raise ConfigError("dominance_threshold must be in (0.5, 1.0)")

        if int(w["tiers"]["max_tiers"]) < 2:
            raise ConfigError("tiers.max_tiers must be >= 2")


def load_config() -> Config:
    weights = yaml.safe_load((CONFIG_DIR / "weights.yaml").read_text())
    sources = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text())
    return Config(weights, sources)
