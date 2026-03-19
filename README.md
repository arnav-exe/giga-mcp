# instant-context

## Explanation of Tier Precedence:
The 'tier' of an 'llms*.txt' source dictates how trustworthy/reliable it is. Sources from higher tiers will be prioritzed
- tier 1: files at root (`/llms.txt`, `/llms-full.txt`)
- tier 2: subpath files (`/docs/.../llms.txt`, `/latest/llms.txt`, versioned doc indexes) (these have lower priority, as they may be out of date or for an older version)

# TODO:
  - test all processes that touch the squee lite db

# Quickstart

```bash
pip install -r requirements.txt
python -m instant_context
```
