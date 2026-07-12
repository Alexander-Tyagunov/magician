Transformers core (HF, v5.x). v5: `dtype=` replaces deprecated `torch_dtype`; Trainer takes `processing_class=` (not `tokenizer=`) and `eval_strategy=`. PyTorch backend; `device_map`/big models need `accelerate`.

DO inference via `pipeline(task="text-generation", model="org/name", dtype=torch.bfloat16, device_map="auto")` — prefer bf16 over fp16; single GPU `device=0`, Apple `device="mps"`.
DO pin reproducibility: `revision="<sha>"` on pipeline/`from_pretrained`; `set_seed(n)`.
DO fit big/OOM models with `device_map="auto"` + quant: `model_kwargs={"quantization_config": BitsAndBytesConfig(load_in_4bit=True)}`.
DO stream large data lazily (generator / `KeyDataset`), tokenize `truncation=True` + `padding`.
DO train: `Trainer(model, args, train_dataset=tr, eval_dataset=ev, processing_class=tok)`, `TrainingArguments(bf16=True, eval_strategy="steps")`.

DON'T hardcode HF tokens — `HF_TOKEN` env / `hf auth login`.
DON'T set `batch_size` blindly — skip batching on CPU or latency-bound; batch only when seq length is regular + handle OOM.
DON'T run unaudited checkpoints with `trust_remote_code=True`.
DON'T infer without `model.eval()` + `torch.inference_mode()`; DON'T retokenize per-row in Python loops.
DON'T fine-tune without a held-out eval split (leakage).

Commands: `pip install -U transformers accelerate`; `hf auth login`; `hf download org/model`.

Deep dive when writing non-trivial transformers — read lore/transformers/{pipelines-and-finetuning}.md

Sources: https://huggingface.co/docs/transformers (index, pipeline_tutorial, main_classes/trainer)
