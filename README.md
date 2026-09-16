# kangaroo140

GPU (CUDA) Pollard's Kangaroo solver for Bitcoin Puzzle #140, packaged as a
Docker image, built via GitHub Actions, deployed on vast.ai on an
RTX 4070 Ti Super, with Telegram notifications.

## Target

- Pubkey: `031f6a332d3c5c4f2de2378c012f429cd109ba07d69690c6c701b6bb87860d6640`
- Range: `80000000000000000000000000000000000` : `fffffffffffffffffffffffffffffffffff` (hex)

These are passed in as env vars at container run time, not baked into the
image, so the same image works for any pubkey/range you point it at later.

## 1. Repo layout

```
kangaroo140/
├── Dockerfile
├── entrypoint.py
├── notify.py
└── .github/workflows/docker-publish.yml
```

Push this to a new GitHub repo (e.g. `ouhly10/kangaroo140`). The workflow
builds on every push to `main` and publishes to GHCR at
`ghcr.io/ouhly10/kangaroo140`.

> By default the Dockerfile builds `JeanLucPons/Kangaroo` — the standard,
> actively-used GPU Kangaroo implementation. If you'd rather build your own
> fork (e.g. `ouhly10/Kangaroo777`), just override the build arg:
> `docker build --build-arg KANGAROO_REPO=https://github.com/ouhly10/Kangaroo777.git .`
> — the rest of the pipeline (entrypoint, notifications, vast.ai steps) is
> unchanged as long as the fork keeps the same `-gpu -gpuId -o <file> <work file>`
> CLI shape.

GHCR image visibility defaults to private; if you want vast.ai to pull it
without auth, make the package public in the repo's package settings, or
give vast.ai a GHCR read token (see step 3).

## 2. Make the GHCR package public (simplest path)

GitHub repo → **Packages** → `kangaroo140` → Package settings → Change
visibility → Public. This avoids having to hand vast.ai a registry
credential.

## 3. Launch on vast.ai

- Search offers filtered to **RTX 4070 Ti Super**.
- Custom image: `ghcr.io/ouhly10/kangaroo140@sha256:<digest-from-Actions-log>`
  (pin the digest, not `:latest` — an already-running instance keeps its own
  process regardless of what you push later).
- Docker options / on-start environment variables:

  ```
  PUBKEY=031f6a332d3c5c4f2de2378c012f429cd109ba07d69690c6c701b6bb87860d6640
  RANGE_START=80000000000000000000000000000000000
  RANGE_END=fffffffffffffffffffffffffffffffffff
  TELEGRAM_BOT_TOKEN=<your bot token>
  TELEGRAM_CHAT_ID=<your chat id>
  INSTANCE_TAG=puzzle140-vast1
  GPU_ID=0
  ```

- No exposed ports are needed — this is a pure batch job, not a web app like
  your `btc71-hunter` dashboard. All status/results go through Telegram and
  the container's own logs.

## 4. What you'll get on Telegram

- 🚀 a start message with pubkey, range, and GPU id the moment the container boots
- ⏳ a heartbeat every ~30 minutes so you know a rented instance is still alive
- ✅ the private key **the instant** it's found — sent before anything else,
  so a preempted/killed instance can't cost you the result
- 🛑 a message if the process exits without a result, so you know to relaunch

## 5. Splitting the range across multiple instances (optional)

Since Puzzle #140's range is far too large for one GPU in practical time,
you'll likely want several vast.ai instances each covering a sub-range.
Simplest approach: launch N instances with the same image but different
`RANGE_START`/`RANGE_END` slices and a distinct `INSTANCE_TAG` per one, so
Telegram messages tell you which instance found it. If you want the
quarter-splitting / prefix-exclusion logic from your `btc71-hunter`
generator ported over here, that's a natural next step — just say so and
I'll adapt `generate_custom_starts.py`'s approach to Kangaroo's range-based
input instead of VanitySearch's prefix-based one.
