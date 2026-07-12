# pytorch — Training loop & autograd

Verified against **PyTorch 2.13** stable docs (docs.pytorch.org). Assumes separate python foundation lore. State your torch version; APIs below are 2.x. `torch.compile` is 2.0+.

```python
import torch
print(torch.__version__, torch.cuda.is_available(), torch.backends.mps.is_available())
```

## Device

DO pick device once, move both model and data:
```python
device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
model = model.to(device)
# per batch:
X, y = X.to(device, non_blocking=True), y.to(device, non_blocking=True)
```

- DO reassign for tensors: `x = x.to(device)` — tensor `.to()` is NOT in-place (returns a copy). `model.to(device)` *is* in-place for `nn.Module`, but reassign anyway for clarity.
- DO create optimizer *after* moving the model to device.
- DON'T leave data on CPU while the model is on GPU — `RuntimeError: expected all tensors on same device`.
- DON'T `.cuda()` unconditionally; branch on availability so code runs on CPU/mps.

## Autograd

- `requires_grad=True` records ops into the backward graph. Default `False`, except `nn.Parameter` (always tracked). Graph is rebuilt every forward → arbitrary Python control flow works.
- `loss.backward()` **accumulates** into leaf `.grad` (adds, not replaces). This is why you must zero.
- Freeze layers with `p.requires_grad_(False)` (fine-tuning); still call `optimizer.zero_grad()`.

DO — canonical training loop, correct order:
```python
model.train()
for X, y in train_loader:
    X, y = X.to(device), y.to(device)
    optimizer.zero_grad()          # clear stale grads
    pred = model(X)                # forward
    loss = loss_fn(pred, y)
    loss.backward()                # accumulate grads
    optimizer.step()              # update weights
```
`zero_grad → forward → backward → step`. Equivalent: put `zero_grad()` last; only rule that matters is **zero between `backward()` calls**.

- DON'T forget `zero_grad()` — grads from prior steps sum in, corrupting updates (a top silent bug).
- DON'T call `optimizer.step()` before `loss.backward()`.
- DON'T retain the graph across steps; keep only scalars: `running_loss += loss.item()` (`.item()`/`.detach()` drops graph refs and prevents memory leaks).
- Gradient accumulation (large effective batch): divide loss, step every N:
  ```python
  loss = loss_fn(pred, y) / accum
  loss.backward()
  if (i + 1) % accum == 0:
      optimizer.step(); optimizer.zero_grad()
  ```
- `zero_grad(set_to_none=True)` is the default in 2.x (faster, sets grads to `None`).

## nn.Module / forward

- Subclass `nn.Module`; define layers in `__init__`, computation in `forward`.
- DO call the module — `model(x)` — never `model.forward(x)` (skips hooks).
- Register submodules/params as attributes so `.parameters()`, `.to()`, `.state_dict()` find them; use `nn.ModuleList`/`nn.ModuleDict` for containers (plain `list` is invisible to autograd/device moves).

## Dataset / DataLoader

- Map-style `Dataset`: implement `__len__` + `__getitem__`. Wrap in `DataLoader(ds, batch_size=..., shuffle=True, num_workers=N, pin_memory=True)`.
- DO `shuffle=True` for train, `False` for val/test.
- DO `pin_memory=True` + `.to(device, non_blocking=True)` for faster host→GPU copies.
- DON'T do heavy CPU work in the loop body that belongs in `__getitem__`/workers.

## train() / eval() / no_grad

Two orthogonal switches — set BOTH for inference:

- `model.eval()` / `model.train()` — flips Dropout & BatchNorm behavior ONLY. Does **not** disable grad.
- `torch.no_grad()` — disables graph tracking (saves memory/time). Does **not** change layer behavior.

DO — inference / eval loop:
```python
model.eval()
with torch.no_grad():                # or torch.inference_mode()
    for X, y in val_loader:
        X, y = X.to(device), y.to(device)
        pred = model(X)
        metric.update(pred, y)
model.train()
```

- DON'T compute validation metrics under grad — memory blows up, graph leaks.
- DON'T forget `model.eval()` before validating — BN/Dropout stay in train mode → wrong numbers.
- `torch.inference_mode()` is the faster superset of `no_grad` (2.x). Fall back to `no_grad` if you hit "inference tensor" errors (its outputs can't re-enter autograd).

## AMP (automatic mixed precision)

Current API is `torch.amp` (`torch.cuda.amp.*` is deprecated). CUDA fp16 needs a `GradScaler`; CPU/bf16 does not.

```python
scaler = torch.amp.GradScaler("cuda")
for X, y in train_loader:
    X, y = X.to(device), y.to(device)
    optimizer.zero_grad()
    with torch.autocast(device_type="cuda", dtype=torch.float16):
        loss = loss_fn(model(X), y)   # wrap forward + loss ONLY
    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()
```

- DO wrap only forward+loss in `autocast`; run `backward` outside it.
- DON'T manually `.half()` the model/inputs when autocasting.
- CPU: `with torch.autocast("cpu", dtype=torch.bfloat16):` — no scaler.
- bf16 has fp32's dynamic range (8-bit exponent) so it needs no `GradScaler` — at the cost of less precision than fp16; prefer it on Ampere+ / CPU.

## torch.compile (2.x speedup)

```python
model = torch.compile(model)                      # default
model = torch.compile(model, mode="max-autotune") # best kernels, longer warmup
```

- `mode`: `"default"`, `"reduce-overhead"` (CUDA graphs, small batches), `"max-autotune"`.
- `fullgraph=True` errors on graph breaks (forces one graph); `dynamic=True` avoids recompiles on changing shapes.
- DO compile once (module or fn), then run your normal loop — compatible with autocast/AMP/DDP.
- DON'T recompile every step or wrap inside the loop; first iterations are slow (tracing) — warm up before timing.
- DON'T expect gains on tiny models / CPU-bound tiny batches.

## Reproducibility

DO seed everything at startup:
```python
import random, numpy as np, torch
def set_seed(s=0):
    random.seed(s); np.random.seed(s); torch.manual_seed(s)  # seeds CPU+CUDA
set_seed(0)
```

- DataLoader workers need `worker_init_fn` + a seeded `generator` to be deterministic (each worker reseeds `numpy`/`random` from `torch.initial_seed()`).
- Full determinism: `torch.use_deterministic_algorithms(True)`, `torch.backends.cudnn.deterministic=True`, `torch.backends.cudnn.benchmark=False` (slower).
- DON'T expect bit-identical results across torch versions, platforms, or CPU vs GPU — not guaranteed.

## Checklist

- [ ] Model + every batch on same device (`.to(device)` reassigned for tensors)
- [ ] `optimizer.zero_grad()` every step
- [ ] Order: zero → forward → backward → step
- [ ] `model.eval()` + `no_grad`/`inference_mode` for validation
- [ ] Metrics/logging use `.item()`/`.detach()`, not live graph tensors
- [ ] AMP via `torch.amp` (+ `GradScaler` for CUDA fp16)
- [ ] Seeds set (torch/numpy/random + DataLoader generator)

## Sources

- https://docs.pytorch.org/docs/2.13/notes/autograd.html
- https://docs.pytorch.org/docs/2.13/amp.html
- https://docs.pytorch.org/docs/2.13/generated/torch.compile.html
- https://docs.pytorch.org/docs/2.13/notes/randomness.html
- https://docs.pytorch.org/tutorials/beginner/basics/optimization_tutorial.html
- https://docs.pytorch.org/docs/stable/
