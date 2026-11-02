#!/usr/bin/env bash
# Stages the planning-negative-control fixture: a README with one misspelled word.
set -eu
cat > README.md <<'MD'
# notify

`notify` sends a message to every subscriber of a channel.

Subscribers recieve each message once, in the order it was sent.

## Usage

    notify send --channel builds "Deploy finished"
MD
