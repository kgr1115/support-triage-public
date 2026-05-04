---
name: Bug report
about: Something is producing wrong output, crashing, or behaving unexpectedly
title: "[bug] "
labels: bug
---

## What happened

A clear description of what you expected vs what you got.

## Steps to reproduce

1.
2.
3.

## Environment

- OS:
- Python version (`python --version`):
- Node version (`node --version`):
- Branch / commit SHA you're on:
- API key set? (yes/no — but never paste the key)

## Eval impact (if applicable)

If this is a quality regression (faithfulness, recall@k, classifier accuracy), include:
- The eval command you ran (`make eval-classifier`, etc.)
- Before / after numbers if known
- The fixture set used (the committed `fixtures/synthetic/` or your own data)

## Logs / output

Paste relevant stack traces or log lines. Redact any customer data.
