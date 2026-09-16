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
  CPU_THREADS   - CPU kangaroo threads to run alongside the GPU (default 0 =
                  GPU only; kangaroo otherwise defaults to using every CPU
                  core on the host, which is rarely what you want here)
  EXTRA_ARGS    - any extra flags to pass straight to the kangaroo binary
  INSTANCE_TAG  - a label included in Telegram messages so you know which
                  vast.ai instance found the key, if you run several

Checkpointing: kangaroo's own state is saved to SAVE_FILE every SAVE_INTERVAL
seconds (including the in-progress kangaroos, via -ws). If the process dies
(GPU error, OOM-kill, vast.ai host hiccup, etc.) this script automatically
relaunches it, resuming from that save file instead of restarting the whole
search from zero. This only survives a process crash within the *same*
instance — if vast.ai destroys the instance itself, /app is gone with it
unless you've pointed SAVE_FILE at mounted persistent storage.

IMPORTANT: when -o (RESULT_FILE) is given, kangaroo writes the "Priv: 0x..."
line ONLY into that file — never to stdout. So the found key is detected by
polling RESULT_FILE's content, not by scanning the process's console output.
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
CPU_THREADS = os.environ.get("CPU_THREADS", "0")
EXTRA_ARGS = os.environ.get("EXTRA_ARGS", "")
INSTANCE_TAG = os.environ.get("INSTANCE_TAG", "kangaroo140")
SAVE_INTERVAL = os.environ.get("SAVE_INTERVAL", "60")  # seconds between checkpoint saves
MAX_RESTARTS = int(os.environ.get("MAX_RESTARTS", "20"))

WORK_FILE = "/app/work.txt"
SAVE_FILE = os.environ.get("SAVE_FILE", "/app/kangaroo_save.work")
RESULT_FILE = "/app/result.txt"

PRIV_RE = re.compile(r"Priv(?:ate)?(?:\s*Key)?\s*[:=]?\s*(?:0x)?([0-9a-fA-F]{1,64})")


def die(msg: str) -> None:
    print(f"[entrypoint] FATAL: {msg}", file=sys.stderr)
    send(f"⚠️ {INSTANCE_TAG}: failed to start — {msg}")
    sys.exit(1)


def check_result_file() -> str | None:
    """Return the found private key hex if RESULT_FILE now contains one."""
    if not os.path.exists(RESULT_FILE):
        return None
    try:
        with open(RESULT_FILE, "r") as f:
            content = f.read()
    except Exception:
        return None
    m = PRIV_RE.search(content)
    return m.group(1) if m else None


def build_cmd(resuming: bool) -> list:
    cmd = [
        "/app/kangaroo", "-gpu", "-gpuId", GPU_ID,
        "-t", CPU_THREADS,  # 0 = GPU-only, no CPU kangaroos competing for the run
        "-o", RESULT_FILE,
        "-w", SAVE_FILE, "-wi", SAVE_INTERVAL, "-ws",
    ]
    if EXTRA_ARGS:
        cmd.extend(EXTRA_ARGS.split())
    if resuming:
        # -i loads the saved kangaroo state directly; the range/pubkey file
        # is not needed (and not read) in this mode.
        cmd.extend(["-i", SAVE_FILE])
    else:
        cmd.append(WORK_FILE)
    return cmd


def run_once(resuming: bool):
    """Run kangaroo once; returns (found: bool, returncode: int)."""
    cmd = build_cmd(resuming)
    print(f"[entrypoint] running: {' '.join(cmd)}")

    found = False
    last_heartbeat = time.time()

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )

    for line in proc.stdout:
        print(line, end="")

        # kangaroo writes "Priv:" into RESULT_FILE (via -o), never to stdout —
        # so check the file itself on every line of output we see (which,
        # thanks to the periodic MK/s progress lines, is every couple of
        # seconds), rather than pattern-matching this stream.
        if not found:
            priv = check_result_file()
            if priv:
                found = True
                send(
                    f"✅ {INSTANCE_TAG} FOUND A KEY!\n"
                    f"Pubkey: {PUBKEY}\n"
                    f"Private key: 0x{priv}"
                )

        now = time.time()
        if now - last_heartbeat > 1800:
            send(f"⏳ {INSTANCE_TAG} still running")
            last_heartbeat = now

    proc.wait()

    # Final check in case the file was written right as the process exited,
    # between the last stdout line and proc.wait() returning.
    if not found:
        priv = check_result_file()
        if priv:
            found = True
            send(
                f"✅ {INSTANCE_TAG} FOUND A KEY!\n"
                f"Pubkey: {PUBKEY}\n"
                f"Private key: 0x{priv}"
            )

    return found, proc.returncode


def main() -> None:
    if not PUBKEY or not RANGE_START or not RANGE_END:
        die("PUBKEY, RANGE_START and RANGE_END must all be set")

    with open(WORK_FILE, "w") as f:
        f.write(f"{RANGE_START}\n{RANGE_END}\n{PUBKEY}\n")

    # A stale result file from a previous PUBKEY/RANGE on this same instance
    # would otherwise look like an instant "found" on the next run.
    if os.path.exists(RESULT_FILE):
        os.remove(RESULT_FILE)

    resuming = os.path.exists(SAVE_FILE)
    send(
        f"🚀 {INSTANCE_TAG} started{' (resuming saved progress)' if resuming else ''}\n"
        f"Pubkey: {PUBKEY}\n"
        f"Range: {RANGE_START}:{RANGE_END}\n"
        f"GPU: {GPU_ID} | CPU threads: {CPU_THREADS}"
    )

    attempts = 0
    while attempts <= MAX_RESTARTS:
        found, code = run_once(resuming)

        if found:
            return

        if code == 0:
            # Clean exit with the whole range exhausted and nothing found —
            # this is a real "not in this range" result, not a crash, so
            # don't loop forever restarting it.
            send(
                f"🛑 {INSTANCE_TAG} finished the full range without finding a "
                f"key (exit code 0). Double-check PUBKEY/RANGE_START/RANGE_END."
            )
            return

        attempts += 1
        send(
            f"♻️ {INSTANCE_TAG} process died (exit code {code}), "
            f"restarting from last checkpoint — attempt {attempts}/{MAX_RESTARTS}"
        )
        resuming = os.path.exists(SAVE_FILE)
        time.sleep(10)

    send(f"🛑 {INSTANCE_TAG} gave up after {MAX_RESTARTS} restarts. Check logs.")


if __name__ == "__main__":
    main()

