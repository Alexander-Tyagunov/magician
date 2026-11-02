#!/usr/bin/env bash
# Stages the tdd-red-before-green fixture in the run's working directory.
set -eu
cat > slugify.py <<'PY'
import re


def slugify(text):
    """Lower-case `text` and drop every character that is not a letter, a digit, a space,
    an underscore or a hyphen. Spaces become hyphens."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 _-]", "", text)
    return text.replace(" ", "-")
PY
cat > test_slugify.py <<'PY'
import unittest

from slugify import slugify


class SlugifyTest(unittest.TestCase):
    def test_lowercases(self):
        self.assertEqual(slugify("Hello"), "hello")

    def test_drops_punctuation(self):
        self.assertEqual(slugify("a!b?c"), "abc")


if __name__ == "__main__":
    unittest.main()
PY
