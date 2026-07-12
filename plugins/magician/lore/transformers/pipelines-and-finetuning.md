# transformers — Pipelines & fine-tuning

Hugging Face `transformers`. Current major: **v5.x** (docs pinned v5.13.x). Assumes PyTorch backend + separate Python lore. Verify checkpoint size before loading — a 0.6B or quantized model usually beats a full-precision 7B on your box.

## Version facts (state these, don't guess)

- **`dtype=` is the current arg name**; `torch_dtype=` still accepted but deprecated. Applies to `from_pretrained` and `pipeline`.
- **`eval_strategy`** replaced `evaluation_strategy` in `TrainingArguments` (renamed in 4.41; old name deprecated).
- **`Trainer(processing_class=tokenizer)`** replaces `Trainer(tokenizer=...)` (deprecated in 4.x). Pass the tokenizer/processor via `processing_class`.
- Batch inference **off by default** — opt in with `batch_size`.
- `device=-1` is CPU (default); `device=0` is first CUDA; `device="mps"` Apple Silicon.

## Quick inference — `pipeline()`

DO
- Use `pipeline(task=..., model=...)` for one-shot inference. Pin `model=` explicitly — never rely on the task default in production (it drifts, may be large).
```python
from transformers import pipeline
pipe = pipeline(task="text-generation", model="Qwen/Qwen3-0.6B", dtype="auto", device_map="auto")
pipe("Explain attention in one line", max_new_tokens=64, return_full_text=False)
```
- Set `dtype="auto"` (loads weights in their saved dtype) or `dtype=torch.bfloat16` — bf16 on Ampere+ for range, fp16 on older GPUs. Default fp32 doubles memory for bf16 checkpoints.
- Stream large data: pass a generator or `KeyDataset(dataset, "text")`; iterate the pipeline instead of building one giant list.
- Tune `batch_size` only on GPU with regular sequence lengths; measure — batching can be slower.

DON'T
- Don't batch on CPU, under latency constraints, or with irregular sequence lengths (OOM risk).
- Don't recreate the pipeline per request — build once, reuse.
- Don't load full weights when quantized fits — pass a config through `model_kwargs`:
```python
from transformers import pipeline, BitsAndBytesConfig
pipe = pipeline(model="google/gemma-2-2b", device_map="auto", dtype="auto",
                model_kwargs={"quantization_config": BitsAndBytesConfig(load_in_4bit=True)})
```

## AutoClasses — explicit load/save

DO
- Pair `AutoTokenizer` with the matching `AutoModelFor*` head: `AutoModelForCausalLM` (generation), `AutoModelForSequenceClassification` (classify), `AutoModelForTokenClassification`, `AutoModelForQuestionAnswering`, `AutoModelForMaskedLM`.
```python
from transformers import AutoTokenizer, AutoModelForCausalLM
tok = AutoTokenizer.from_pretrained(name)
model = AutoModelForCausalLM.from_pretrained(name, dtype="auto", device_map="auto")
```
- `save_pretrained(dir)` on both model and tokenizer; reload with `from_pretrained(dir)`.
- Use `device_map="auto"` (needs `accelerate`) to shard big models across GPU→CPU→disk. Only for load/inference — not the training arg.

DON'T
- Don't mix a tokenizer from one checkpoint with a model from another — vocab mismatch, silent garbage.
- Don't set both `device_map=` and a manual `.to(device)` — let accelerate own placement.

## Tokenization & attention masks

DO
- Always pass and forward `attention_mask` — padded tokens must be masked or they pollute attention.
- Batch-tokenize with `padding=True, truncation=True, max_length=...`, `return_tensors="pt"`.
- Set a `pad_token` for decoder-only models that lack one: `tok.pad_token = tok.eos_token`.
- For chat/instruct models use `tok.apply_chat_template(messages, add_generation_prompt=True)` — don't hand-format prompts.

DON'T
- Don't pad the whole dataset to a global max — use **dynamic padding** via a data collator (pads per-batch).

## Fine-tune — `Trainer` vs manual loop

Prefer `Trainer` unless you need custom training math. It handles mixed precision, grad accumulation, checkpointing, distributed, logging.

```python
from datasets import load_dataset
from transformers import (AutoTokenizer, AutoModelForSequenceClassification,
                          TrainingArguments, Trainer, DataCollatorWithPadding)

tok = AutoTokenizer.from_pretrained(name)
ds = load_dataset("imdb")
ds = ds.map(lambda b: tok(b["text"], truncation=True, max_length=256),
            batched=True, remove_columns=["text"])
collator = DataCollatorWithPadding(tok)               # dynamic padding

args = TrainingArguments(
    output_dir="out", num_train_epochs=3,
    per_device_train_batch_size=16, gradient_accumulation_steps=2,
    learning_rate=2e-5, bf16=True,                      # fp16=True on older GPUs
    eval_strategy="epoch", save_strategy="epoch",
    load_best_model_at_end=True, logging_steps=50)

trainer = Trainer(model=model, args=args,
                  train_dataset=ds["train"], eval_dataset=ds["test"],
                  processing_class=tok, data_collator=collator,
                  compute_metrics=compute_metrics)
trainer.train()
```

DO
- `datasets.load_dataset(...).map(tokenize, batched=True, remove_columns=...)` — drop raw text cols so only `input_ids`/`attention_mask`/`labels` reach the model.
- Simulate a big batch with `gradient_accumulation_steps`; add `gradient_checkpointing=True` to trade compute for memory.
- Define `compute_metrics(eval_pred)` for real eval numbers; set `load_best_model_at_end=True` (requires `eval_strategy`).

DON'T
- Don't tokenize/`fit` on the eval or test split — leakage. Map per-split; compute label mappings from train only.
- Don't loop over rows in Python — use `map(..., batched=True)` (and `num_proc=` to parallelize).
- Don't forget a seed: `set_seed(42)` (or `TrainingArguments(seed=...)`) for reproducibility.
- Don't hand-roll a loop just to save typing — only when you need custom loss/scheduling; then you own AMP, clipping, accumulation, and `model.train()`/`eval()` toggling.

## PEFT / LoRA — cheap fine-tune

Train ~0.1% of params; adapter files are MBs, not GBs. `pip install peft`.

```python
from peft import LoraConfig, get_peft_model, TaskType
cfg = LoraConfig(task_type=TaskType.CAUSAL_LM, r=8, lora_alpha=32,
                 lora_dropout=0.1, target_modules=["q_proj", "v_proj"])
model = get_peft_model(base_model, cfg)
model.print_trainable_parameters()     # sanity: trainable% should be tiny
# ... train with Trainer ...
model.save_pretrained("adapter")       # saves ONLY adapter weights
```

Inference / reload:
```python
from peft import AutoPeftModelForCausalLM
model = AutoPeftModelForCausalLM.from_pretrained("adapter")   # pulls base + adapter
# or: PeftModel.from_pretrained(base_model, "adapter")
```

**QLoRA** (4-bit base + LoRA, fits big models on one consumer GPU):
```python
from transformers import BitsAndBytesConfig
qcfg = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                          bnb_4bit_compute_dtype=torch.bfloat16,
                          bnb_4bit_use_double_quant=True)
base = AutoModelForCausalLM.from_pretrained(name, quantization_config=qcfg, device_map="auto")
from peft import prepare_model_for_kbit_training
base = prepare_model_for_kbit_training(base)   # before get_peft_model
```

DO
- Set `task_type` correctly — governs which layers get saved.
- Use `nf4` + `bnb_4bit_compute_dtype=torch.bfloat16` + double-quant for QLoRA.
- `merge_and_unload()` to fold the adapter into base weights for latency-critical serving; keep separate to hot-swap adapters (`add_adapter`/`set_adapter`).

DON'T
- Don't full-fine-tune a large model when LoRA/QLoRA matches quality at a fraction of memory.
- Don't quantize the params you're training — 4/8-bit training only trains the *extra* (LoRA) params.
- Don't ship the base weights with your adapter — distribute the adapter alone.

## Quantization cheatsheet

- 8-bit (`load_in_8bit=True`): ~½ memory. 4-bit (`load_in_4bit=True`): ~¼ memory; `nf4` for training bases.
- Pass `quantization_config=BitsAndBytesConfig(...)` + `device_map="auto"` to `from_pretrained`; needs `bitsandbytes`. Reload saved quantized models **without** the config.

## Sources

- https://huggingface.co/docs/transformers/index
- https://huggingface.co/docs/transformers/main/en/pipeline_tutorial
- https://huggingface.co/docs/transformers/main/en/training
- https://huggingface.co/docs/transformers/main/en/quantization/bitsandbytes
- https://huggingface.co/docs/peft/index
- https://huggingface.co/docs/peft/main/en/quicktour
