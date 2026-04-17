Common AI mistakes: forgetting `.zero_grad()` before backward pass; not calling `model.eval()` during inference; tensor dimension mismatches; CPU/GPU device mismatches.
Commands: test: `pytest tests/`, lint: `ruff check .`.
Gotchas: `.detach()` before converting tensor to numpy; `DataLoader` with `num_workers > 0` requires `if __name__ == '__main__'` on Windows; use `torch.no_grad()` context for inference.
