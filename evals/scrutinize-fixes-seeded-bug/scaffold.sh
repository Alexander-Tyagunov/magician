#!/usr/bin/env bash
# Stages the scrutinize-fixes-seeded-bug fixture: a committed pagination.py, then an uncommitted
# change that adds page_count with an off-by-one (an exact multiple gets one page too many).
set -eu
cat > pagination.py <<'PY'
def page(items, number, size):
    """Items on the 1-based page `number`, `size` items per page."""
    start = (number - 1) * size
    return items[start:start + size]
PY
if command -v git >/dev/null 2>&1; then
  git init -q .
  git add pagination.py
  git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "Add page()"
fi
cat >> pagination.py <<'PY'


def page_count(total, size):
    """Number of pages needed to show `total` items, `size` items per page."""
    if size <= 0:
        raise ValueError("size must be positive")
    return total // size + 1
PY
