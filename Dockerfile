# Kangaroo (Pollard's Kangaroo, GPU/CUDA build) for Puzzle #140
# Targets RTX 4070 Ti Super (Ada Lovelace, compute capability 8.9)

FROM nvidia/cuda:12.4.1-devel-ubuntu22.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential libgmp-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Default to JeanLucPons/Kangaroo (the standard, maintained GPU Kangaroo implementation).
# Swap this for your own fork (e.g. ouhly10/Kangaroo777) if you prefer your customized version —
# same build steps apply as long as the fork keeps the same Makefile GPU/CCAP flags.
ARG KANGAROO_REPO=https://github.com/JeanLucPons/Kangaroo.git
RUN git clone --depth 1 ${KANGAROO_REPO} kangaroo

WORKDIR /build/kangaroo
# Kangaroo's own Makefile hardcodes CUDA=/usr/local/cuda-8.0 and
# CXXCUDA=/usr/bin/g++-4.8, and its GPU arch variable is lowercase "ccap"
# (not CCAP) — override all three on the command line so it builds against
# the CUDA toolkit actually present in this image, with the ccap for
# Ada Lovelace (RTX 4070 Ti Super / 4090 / 4080 etc.)
RUN make gpu=1 ccap=89 CUDA=/usr/local/cuda CXXCUDA=/usr/bin/g++ all

# ---- runtime image ----
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir requests cryptography

WORKDIR /app
COPY --from=builder /build/kangaroo/kangaroo /app/kangaroo
COPY entrypoint.py /app/entrypoint.py
COPY notify.py /app/notify.py
COPY encrypt.py /app/encrypt.py

ENTRYPOINT ["python3", "/app/entrypoint.py"]
