# TensorFlow — core lore

Version: TF 2.21 (2026). TF 2.16+ ships Keras 3 (multi-backend TF/JAX/PyTorch) as `tf.keras`. Legacy Keras 2 = `pip install tf_keras` + `TF_USE_LEGACY_KERAS=1` before `import tensorflow`.

DO set `KERAS_BACKEND` env BEFORE `import keras` — backend is fixed after import.
DO save as `.keras` (`model.save("m.keras")`), the native format; not legacy `.h5`.
DO build input via `tf.data`: `ds.cache().shuffle(n).batch(b).prefetch(tf.data.AUTOTUNE)`.
DO wrap hot code in `@tf.function` (graph mode); pass tensors, not Python scalars, to avoid retracing.
DO seed everything: `tf.keras.utils.set_random_seed(0)` + `tf.config.experimental.enable_op_determinism()`.
DO `adapt()` preprocessing layers (e.g. `Normalization`) on TRAIN only — no leakage.
DO GPU: `set_memory_growth(gpu, True)`; scale with `keras.mixed_precision.set_global_policy("mixed_float16")`.
DON'T loop Python over tensor rows — vectorize with TF ops.
DON'T call `.numpy()`, print, or mutate Python state inside `@tf.function`.
DON'T use TF1 `Session`/`placeholder`/`feed_dict` — eager + `tf.function` only.
DON'T mix `keras` and `tf.keras` imports in one project.

Commands: `pip install tensorflow` · `python -c "import tensorflow as tf; print(tf.__version__, tf.config.list_physical_devices('GPU'))"`

Deep dive when writing non-trivial tensorflow — read lore/tensorflow/{keras3-and-training}.md
Sources: tensorflow.org/api_docs · keras.io/getting_started · github.com/tensorflow/tensorflow/releases
