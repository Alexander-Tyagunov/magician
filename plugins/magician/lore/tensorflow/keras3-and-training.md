# tensorflow — Keras 3 & training

Keras 3 is the current recommended API: multi-backend over **TensorFlow, JAX, or PyTorch**.
Assume Python foundation lore exists elsewhere. Verify version facts before asserting.

## Versions & backend (DO)
- DO know: `pip install keras` → **Keras 3**; needs a backend (`tensorflow`, `jax`, or `torch`) installed separately.
- DO know TF coupling: **TF ≤ 2.15** ships Keras 2. **TF ≥ 2.16** ships **Keras 3** as `tf.keras`. TF 2.15 will overwrite Keras 3 with `keras==2.15` — reinstall Keras after.
- DO set backend **before importing keras** — it cannot change after import:
  ```python
  import os
  os.environ["KERAS_BACKEND"] = "jax"   # "tensorflow" | "jax" | "torch"
  import keras
  ```
  Or `export KERAS_BACKEND=jax`, or edit `~/.keras/keras.json`.
- DO write backend-agnostic code with `keras.ops.*` (NumPy-like) instead of raw `tf.*` when you want portability.
- DO set seeds for reproducibility: `keras.utils.set_random_seed(42)`.

## Versions & backend (DON'T)
- DON'T assume `import tensorflow as tf; tf.keras` is Keras 2 — on TF ≥ 2.16 it IS Keras 3.
- DON'T mix raw backend ops (`tf.nn.*`, `torch.*`) into a model you intend to run on other backends.
- DON'T need Keras 2? It lives on as **`tf_keras`**; pin `tf.keras` to legacy with `export TF_USE_LEGACY_KERAS=1`.

## Building models — three ways (DO)
```python
from keras import layers, Model, Sequential, Input

# 1. Sequential — single-input/single-output linear stack
model = Sequential([Input((784,)), layers.Dense(64, activation="relu"),
                    layers.Dense(10, activation="softmax")])

# 2. Functional — arbitrary graphs (multi-in/out, shared, branching). Preferred default.
inp = Input((784,))
x = layers.Dense(64, activation="relu")(inp)
out = layers.Dense(10, activation="softmax")(x)
model = Model(inp, out)

# 3. Subclassing — full control for research
class Net(Model):
    def __init__(self):
        super().__init__()
        self.d1 = layers.Dense(64, activation="relu")
        self.d2 = layers.Dense(10, activation="softmax")
    def call(self, x, training=False):
        return self.d2(self.d1(x))
```
- DO prefer **Functional** for most work; use **Sequential** only for simple stacks; use **subclassing** for dynamic/research logic.
- DO pass `training=` through `call()` so Dropout/BatchNorm behave correctly.

## Building models (DON'T)
- DON'T use Sequential for multi-input/output or branching topologies — it can't express them.
- DON'T call `model.summary()` on a subclassed model before it's built (needs a forward pass or `Input`).

## compile / fit / evaluate / predict (DO)
```python
model.compile(
    optimizer=keras.optimizers.Adam(1e-3),
    loss=keras.losses.SparseCategoricalCrossentropy(),
    metrics=[keras.metrics.SparseCategoricalAccuracy()],
    jit_compile="auto",   # XLA on TF/JAX; torch.compile(inductor) on PyTorch
)
history = model.fit(train_ds, validation_data=val_ds, epochs=20, callbacks=[...])
loss, acc = model.evaluate(test_ds)
preds = model.predict(x_big)          # batched; for one small batch prefer model(x, training=False)
```
- DO match loss to labels: `SparseCategorical*` for integer labels, `Categorical*` for one-hot, `Binary*` for 2-class.
- DO use `class_weight={i: w}` or `weighted_metrics=` for imbalance.
- DO use `verbose=2` (one line/epoch) in logs/CI; `1` (progress bar) interactively.
- DO read results from `history.history` (dict of per-epoch lists).

## compile / fit (DON'T)
- DON'T pass `y` or `batch_size` when `x` is a `tf.data.Dataset` / `DataLoader` / `PyDataset` / generator — they batch and carry targets themselves.
- DON'T change `layer.trainable` after `compile()` without **recompiling** — trainable vars are frozen at compile time (Keras 3).
- DON'T expect `steps_per_execution` on the **PyTorch** backend (unsupported).
- DON'T pass `namedtuple` inputs (ambiguous unpacking); yield plain tuples `(x, y[, sample_weight])`.
- DON'T call `predict()` in a hot loop on tiny inputs — `model(x)` is faster and avoids retracing.

## Callbacks (DO)
```python
cbs = [
    keras.callbacks.EarlyStopping(monitor="val_loss", patience=5,
                                  restore_best_weights=True),
    keras.callbacks.ModelCheckpoint("best.keras", monitor="val_loss",
                                    save_best_only=True),      # MUST end in .keras
    keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=3),
    keras.callbacks.TensorBoard(log_dir="./logs"),
    keras.callbacks.BackupAndRestore(backup_dir="./backup"),   # fault-tolerant resume
]
```
- DO use `EarlyStopping(restore_best_weights=True)` — else you keep the last (often worse) epoch.

## Callbacks (DON'T)
- DON'T give `ModelCheckpoint` a full-model path without `.keras`; for weights-only set `save_weights_only=True` and use `*.weights.h5`.
- DON'T monitor a metric you didn't compile/produce (typo'd `monitor` silently never fires).

## tf.data pipelines (DO)
```python
import tensorflow as tf
ds = (tf.data.Dataset.from_tensor_slices((X, y))
      .shuffle(10_000, seed=42)
      .batch(32)
      .prefetch(tf.data.AUTOTUNE))
```
- DO order ops: map → `cache()` (if it fits) → `shuffle` → `batch` → `prefetch(AUTOTUNE)`.
- DO fit preprocessing/normalization stats on **train only** (`layers.Normalization().adapt(train_ds)`), then apply to val/test — prevents leakage.
- DO use `num_parallel_calls=tf.data.AUTOTUNE` in `map`. `tf.data` works as `fit` input on **any** backend.
- DO vectorize inside `map`; avoid per-row Python.

## tf.data pipelines (DON'T)
- DON'T shuffle after batch (shuffles batch order, not samples) or with a buffer smaller than the dataset for weak shuffling.
- DON'T `adapt`/scale using full-dataset statistics — that leaks test info into training.
- DON'T `cache()` a dataset larger than RAM.

## Saving & export (DO)
```python
model.save("m.keras")                        # full model: arch + weights + compile state
model = keras.models.load_model("m.keras")
model.save_weights("m.weights.h5"); model.load_weights("m.weights.h5")
model.export("serving_dir")                  # TF SavedModel for inference/serving
```
- DO use the single-file **`.keras`** format (default, recommended) for whole models.
- DO register custom objects: `@keras.saving.register_keras_serializable()` + implement `get_config()`.
- DO use **`model.export()`** (or `ExportArchive`) to produce a SavedModel — this replaced `save(save_format="tf")`.

## Saving & export (DON'T)
- DON'T rely on legacy `.h5` for models with custom objects — it's lossy; prefer `.keras`.
- DON'T expect `model.save()` to emit a SavedModel dir anymore — that's now `export()`.
- DON'T load untrusted `.keras`/`.h5` files with custom-object deserialization enabled (arbitrary-code risk).

## Custom train_step (DO)
- DO override `train_step(self, data)` for custom losses/metrics; it is **backend-specific** — TF uses `tf.GradientTape`, JAX uses a stateless `compute_loss_and_updates` + grads, PyTorch uses `loss.backward()`. Write per-backend or use `keras.ops`.

## Sources
- https://keras.io/getting_started/
- https://keras.io/api/models/
- https://keras.io/api/models/model_training_apis/
- https://keras.io/api/models/model_saving_apis/
- https://keras.io/api/callbacks/
- https://www.tensorflow.org/api_docs
- https://www.tensorflow.org/guide/keras
