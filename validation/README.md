# Validation data interface

This directory contains the contract for future criterion-validation data, not a claim of
completed validation. Real recordings are intentionally not committed.

- `manifest.schema.json` defines participant-level splits, protocol, consent, file hashes,
  and de-identified strata.
- `paired_measurements.example.csv` shows the evaluator input. Each row is one synchronized
  GaitLab/criterion pair.
- `scripts/evaluate_validation.py` computes failure rate, bias, MAE, RMSE, and Bland–Altman
  limits by metric and split. Use held-out `test` results for claims.

Run the example:

```bash
python scripts/evaluate_validation.py validation/paired_measurements.example.csv
```

See `docs/validation_protocol.md` before collecting or interpreting data.

