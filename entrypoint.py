#!/usr/bin/env python3
"""
Entrypoint for the Puzzle #140 Kangaroo GPU search container.

Required env vars:
  PUBKEY        - the public key to solve (hex, compressed or uncompressed)
  RANGE_START   - lower bound of the private key range (hex, no 0x prefix ok)
  RANGE_END     - upper bound of the private key range (hex, no 0x prefix ok)

Optional env vars:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  - for notifications (see notify.py)
  GPU_ID        - which GPU to use (default 0)
  EXTRA_ARGS    - any extra flags to pass straight to the kangaroo binary
  INSTANCE_TAG  - a label included in Telegram messages so you know which
                  vast.ai instance found the key, if you run several
"""

import os
import re
import subprocess
import sys
import time

from notify import send

PUBKEY = os.environ.get("PUBKEY", "").strip().lower().replace("0x", "")
RANGE_START = os.environ.get("RANGE_START", "").strip().lower().replace("0x", "")
RANGE_END = os.environ.get("RANGE_END", "").strip().lower().replace("0x", "")
GPU_ID = os.environ.get("GPU_ID", "0")
EXTRA_ARGS = os.environ.get("EXTRA_ARGS", "")
INSTANCE_TAG = os.environ.get("INSTANCE_TAG", "kangaroo140")

WORK_FILE = "/app/work.txt"
RESULT_FILE = "/app/result.txt"

PRIV_RE = re.compile(r"(?:Priv(?:ate)?(?:\s*Key)?)\s*[:=]?\s*(?:0x)?([0-9a-fA-F]{1,64})")


def die(msg: str) -> None:
    print(f"[entrypoint] FATAL: {msg}", file=sys.stderr)
    send(f"⚠️ {INSTANCE_TAG}: failed to start — {msg}")
    sys.exit(1)


def main() -> None:
    if not PUBKEY or not RANGE_START or not RANGE_END:
        die("PUBKEY, RANGE_START and RANGE_END must all be set")

    with open(WORK_FILE, "w") as f:
        f.write(f"{RANGE_START}\n{RANGE_END}\n{PUBKEY}\n")

    send(
        f"🚀 {INSTANCE_TAG} started\n"
        f"Pubkey: {PUBKEY}\n"
        f"Range: {RANGE_START}:{RANGE_END}\n"
        f"GPU: {GPU_ID}"
    )

    cmd = ["/app/kangaroo", "-gpu", "-gpuId", GPU_ID, "-o", RESULT_FILE]
    if EXTRA_ARGS:
        cmd.extend(EXTRA_ARGS.split())
    cmd.append(WORK_FILE)

    print(f"[entrypoint] running: {' '.join(cmd)}")

    found = False
    start_time = time.time()
    last_heartbeat = start_time

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )

    for line in proc.stdout:
        print(line, end="")

        # Send the notification the instant a key line appears — before
        # anything else — so a preempted/killed vast.ai instance can't
        # cost you the result.
        m = PRIV_RE.search(line)
        if m and not found:
            found = True
            priv = m.group(1)
            send(
                f"✅ {INSTANCE_TAG} FOUND A KEY!\n"
                f"Pubkey: {PUBKEY}\n"
                f"Private key: 0x{priv}\n"
                f"Raw line: {line.strip()}"
            )

        # Lightweight heartbeat every ~30 min so you know the instance is
        # still alive on vast.ai without spamming Telegram.
        now = time.time()
        if now - last_heartbeat > 1800:
            elapsed_h = (now - start_time) / 3600
            send(f"⏳ {INSTANCE_TAG} still running ({elapsed_h:.1f}h elapsed)")
            last_heartbeat = now

    proc.wait()

    if not found:
        send(
            f"🛑 {INSTANCE_TAG} exited without finding a key "
            f"(exit code {proc.returncode}). Check logs."
        )


if __name__ == "__main__":
    main()
