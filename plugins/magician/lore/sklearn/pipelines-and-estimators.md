# sklearn — Pipelines & estimators

Version facts verified against scikit-learn **1.9.0** docs (stable, June 2026). API stable since ~1.2; version markers called out below. Assumes Python + NumPy/pandas lore exists separately.

## Estimator API — the contract

Every estimator implements a fixed protocol. Learn it once, applies everywhere.

DO:
- Know the four verbs: `fit(X, y=None)` learns state (stored as `attr_` with trailing underscore); `predict(X)` (predictors); `transform(X)` (transformers); `fit_transform(X, y)` (fit + transform, often optimized). `score(X, y)` for evaluation.
- Set hyperparameters in `__init__` only; learned attributes get a trailing underscore (`scaler.mean_`, `clf.coef_`). This convention drives `clone`, `get_params`, `set_params`.
- Use `get_params()` / `set_params(**kw)` for introspection and grid search. Nested access uses `step__param`.

DON'T:
- DON'T mutate `X`/`y` in `fit`. DON'T do learning work in `__init__`.
- DON'T read `attr_` before `fit` — it won't exist.

## Data leakage — the cardinal sin

> "Never call `fit` on the test data." Statistics (mean, variance, imputation values, feature-selection masks, PCA components) must be learned from **train only**.

DO:
- Split FIRST, before any preprocessing: `X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)`. Use `stratify=y` for classification.
- `fit_transform` on train, `transform` (never fit) on test.
- Wrap preprocessing + model in a `Pipeline` so the leak is structurally impossible — the pipeline fits transformers on the training fold only, inside every CV split.

DON'T:
- DON'T `scaler.fit_transform(X)` on the full dataset then split — leaks test distribution.
- DON'T `SelectKBest(k=25).fit_transform(X, y)` before splitting — leaks the target; drives fake accuracy (0.76 on random data that should score 0.5).
- DON'T forget to transform test with the *fitted* train scaler — inconsistent preprocessing is its own bug.

```python
# WRONG — feature selection / scaling on all data leaks test info
X_sel = SelectKBest(k=25).fit_transform(X, y)
X_tr, X_te, y_tr, y_te = train_test_split(X_sel, y)   # too late

# RIGHT — pipeline confines every fit to the train fold
from sklearn.pipeline import make_pipeline
pipe = make_pipeline(StandardScaler(), SelectKBest(k=25), LogisticRegression())
pipe.fit(X_train, y_train)
pipe.score(X_test, y_test)   # transform applied correctly to test
```

## Pipeline

`from sklearn.pipeline import Pipeline, make_pipeline`

DO:
- All steps except the last must be transformers (have `transform`); the last can be anything (predictor, transformer, clusterer). Pipeline exposes the last step's methods.
- Prefer `make_pipeline(StandardScaler(), SVC())` — auto-names steps (`'standardscaler'`, `'svc'`, lowercased class names).
- Access steps: `pipe['svc']`, `pipe.named_steps.svc`, `pipe[-1]`; slice for a sub-pipeline `pipe[:-1]`.
- Tune nested params with `step__param`: `pipe.set_params(svc__C=10)`.
- Set `memory=<dir>` to cache fitted transformers across grid-search fits (last step never cached; caching clones transformers — inspect via `named_steps`).
- Use `'passthrough'` to skip a non-final step (e.g. toggle `reduce_dim` in a grid).

DON'T:
- DON'T fit steps manually and stitch them — you lose leakage protection and CV correctness.
- DON'T expect `pipe.named_steps['pca'].components_` on the *original* instance when `memory` is set — it clones.

## ColumnTransformer — heterogeneous columns

`from sklearn.compose import ColumnTransformer, make_column_transformer, make_column_selector`

DO:
- Route different transformers to different columns; leakage-safe and grid-tunable inside a Pipeline.
- 2D transformers (`OneHotEncoder`, `StandardScaler`) take a column **list** `['city']`; 1D transformers (`CountVectorizer`) take a **string** `'title'`.
- Select by dtype with `make_column_selector(dtype_include=np.number)` / `dtype_include=object`.
- Control leftover columns via `remainder`: `'drop'` (default), `'passthrough'`, or an estimator (e.g. `MinMaxScaler()`).
- Use `verbose_feature_names_out=False` to keep clean output names when they're already unique.

```python
pre = ColumnTransformer([
    ("num", StandardScaler(), make_column_selector(dtype_include=np.number)),
    ("cat", OneHotEncoder(handle_unknown="ignore"),
            make_column_selector(dtype_include=object)),
], remainder="drop")
model = make_pipeline(pre, LogisticRegression())
```

DON'T:
- DON'T mix a 2D transformer with a scalar (string) column spec, or vice versa — shape errors.
- DON'T assume integer column indices for a DataFrame; integers are always positional, strings match names.

## pandas / polars output

`transform_output` added in **1.2**; `"polars"` added in **1.4**.

DO:
- Global: `from sklearn import set_config; set_config(transform_output="pandas")` (or `"polars"`).
- Per-estimator: `scaler.set_output(transform="pandas")`.
- Scoped: `with config_context(transform_output="pandas"): ...`.
- Pair with `get_feature_names_out()` (on Pipeline/ColumnTransformer) to keep named columns through the chain.

DON'T:
- DON'T rely on positional NumPy columns after a `ColumnTransformer` reorders/one-hot-expands — request pandas output and read by name.

## Cross-validation & tuning

`from sklearn.model_selection import cross_val_score, GridSearchCV, RandomizedSearchCV, KFold, StratifiedKFold`

DO:
- Pass the **whole pipeline** to `cross_val_score(pipe, X, y, cv=5)` / `GridSearchCV` — each fold re-fits preprocessing on its own train split. This is the only correct way to estimate generalization.
- Grid over nested params: `GridSearchCV(pipe, {"selectkbest__k": [10, 25], "logisticregression__C": [0.1, 1, 10]}, cv=5)`.
- Use `StratifiedKFold` (default for classifier `cv=int`) to preserve class ratios; `RandomizedSearchCV` when the grid is large.
- After tuning, `grid.best_estimator_` is already refit on all data (`refit=True` default); use it directly.

DON'T:
- DON'T tune/select features outside CV (leaks). DON'T report `best_score_` as final test performance — keep a held-out test set.

## Reproducibility — random_state

DO:
- Estimators/splitters that randomize expose `random_state`. For repeatable runs, thread one generator: `rng = np.random.RandomState(0)` and pass it everywhere (or pass a fixed integer).
- Pass an **integer** to CV splitters (`KFold(shuffle=True, random_state=0)`) so folds are identical across separate `GridSearchCV`/`cross_val_score` calls — valid comparison.
- Integer `random_state` → identical results each `fit`; `RandomState` instance / `None` → varies each call.

DON'T:
- DON'T set `np.random.seed(...)` globally (docs advise against it) — thread `random_state` explicitly instead.
- DON'T leave `random_state=None` if you need cross-run reproducibility.
- Note: passing a `RandomState` *instance* makes `clone()` a statistical (shared-RNG) copy, not an exact one — matters inside `GridSearchCV`/`StackingClassifier`. Pass an integer for exact independent clones.

## Target transforms & feature union

- `TransformedTargetRegressor(regressor=..., transformer=...)` or `func`/`inverse_func` — transforms `y` (e.g. log) and inverts predictions. Don't set both a transformer and the func pair.
- `FeatureUnion` / `make_union` — fit transformers in parallel, concatenate outputs side-by-side; you must ensure feature sets are disjoint.

## Sources
- https://scikit-learn.org/stable/modules/compose.html
- https://scikit-learn.org/stable/common_pitfalls.html
- https://scikit-learn.org/stable/modules/generated/sklearn.set_config.html
- https://scikit-learn.org/stable/ (version 1.9.0, stable)
