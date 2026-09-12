#!/usr/bin/env python3
"""Summarize paired GaitLab/criterion measurements from a validation CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


REQUIRED = {"participant_id", "split", "trial_id", "metric", "unit", "observed", "criterion", "failure_reason"}


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["split"], row["metric"], row["unit"])].append(row)

    output = []
    for (split, metric, unit), group in sorted(groups.items()):
        errors = []
        failures = 0
        for row in group:
            try:
                observed = float(row["observed"])
                criterion = float(row["criterion"])
            except (TypeError, ValueError):
                failures += 1
                continue
            if not (math.isfinite(observed) and math.isfinite(criterion)):
                failures += 1
                continue
            errors.append(observed - criterion)

        result = {
            "split": split,
            "metric": metric,
            "unit": unit,
            "n_trials": len(group),
            "n_valid": len(errors),
            "failure_rate": round(failures / len(group), 4),
        }
        if errors:
            bias = mean(errors)
            result.update({
                "bias": round(bias, 4),
                "mae": round(mean(abs(value) for value in errors), 4),
                "rmse": round(math.sqrt(mean(value * value for value in errors)), 4),
            })
            if len(errors) >= 2:
                sd = stdev(errors)
                result["loa95"] = [round(bias - 1.96 * sd, 4), round(bias + 1.96 * sd, 4)]
        output.append(result)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    with args.csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            parser.error(f"missing columns: {', '.join(sorted(missing))}")
        results = summarize(list(reader))

    payload = json.dumps({"results": results}, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

