# sklearn (core)

Version: scikit-learn 1.9 (Jun 2026). set_output 1.2+; TunedThresholdClassifierCV + FixedThresholdClassifier 1.5; `__sklearn_tags__` 1.6.

DO wrap ALL preprocessing (scale/impute/encode/select) in Pipeline/ColumnTransformer; it fits transformers on train folds only.
DON'T fit a scaler/imputer/selector on full X before splitting or CV — leaks test stats. Never .fit on test; fit(train) then transform(test).
DO pass the whole Pipeline to cross_val_score/GridSearchCV so transformers refit each fold. Tune nested params via step__param.
DO set random_state on every estimator, splitter, and split for reproducibility.
DO train_test_split(..., stratify=y) for classification.
DO set_output(transform="pandas") (or "polars") to keep column names through transforms.
DO give ColumnTransformer 2D transformers a list of cols (["city"]); select with make_column_selector(dtype_include=...).
DON'T judge imbalanced data by accuracy — set scoring (f1/roc_auc/average_precision); don't assume 0.5, tune with TunedThresholdClassifierCV.
DO prefer HistGradientBoosting{Classifier,Regressor} for tabular (fast, native NaN) before manual imputation.
DON'T leak the target: use TransformedTargetRegressor for y transforms; fit encoders inside the pipeline.

Commands: pip install -U scikit-learn

Deep dive when writing non-trivial sklearn — read lore/sklearn/{pipelines-and-estimators}.md

Sources: scikit-learn.org/stable/modules/compose.html · /common_pitfalls.html · /whats_new/v1.9.html
