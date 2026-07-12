PyTorch core (stable 2.x; 2.13). torch.compile is stable — DO `model = torch.compile(model)` (mode="reduce-overhead" small batch, "max-autotune" throughput); compile once, not per step.

DO `optimizer.zero_grad(set_to_none=True)` each iter; order = zero_grad → forward → `loss.backward()` → `optimizer.step()`.
DO `model.eval()` + `torch.inference_mode()` for eval (faster than `no_grad`); return to `model.train()` after.
DO pick device once: `dev="cuda" if torch.cuda.is_available() else "cpu"` (or `torch.accelerator.current_accelerator()`, 2.6+); `.to(dev)` model AND every batch — mismatch = RuntimeError.
DO AMP device-agnostic: `with torch.autocast(dev):` + `scaler=torch.amp.GradScaler()`, `scaler.scale(loss).backward(); scaler.step(opt); scaler.update()`.
DO seed: `torch.manual_seed(s)` (+cuda); DataLoader `num_workers>0` needs `if __name__=="__main__":` guard.
DO `loss.item()`/`.detach()` when logging metrics — else you retain the graph and OOM.

DON'T `torch.cuda.amp.autocast` (deprecated → `torch.amp`); DON'T `.numpy()` a grad/GPU tensor — `.detach().cpu().numpy()`.
DON'T train with `no_grad`/`inference_mode` on; DON'T skip `zero_grad` (grads accumulate); DON'T `.cuda()` blindly — gate on availability.

Commands: `pytest tests/`; `ruff check .`; `python -c "import torch;print(torch.__version__,torch.cuda.is_available())"`.

Deep dive when writing non-trivial pytorch — read lore/pytorch/{training-and-autograd}.md

Sources: https://docs.pytorch.org/docs/stable/ (2.13: torch.compile, amp, inference_mode, autograd)
