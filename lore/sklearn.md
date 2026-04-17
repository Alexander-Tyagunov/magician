Common AI mistakes: fitting scaler/encoder on the full dataset (causes data leakage); not using Pipeline to prevent leakage; forgetting to set `random_state`; comparing models trained on different splits.
Commands: test: `pytest`.
Gotchas: always fit on training set, transform on both; `Pipeline` chains preprocessing and model; `cross_val_score` for unbiased evaluation.
