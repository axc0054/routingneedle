#!/bin/bash
# RoutingNeedle — P5000 Qwen3.6-35B-A3B server
# Gates 0-8 validated: ncmoe=16, c=8192, 12,597 MiB peak (supersedes 30B-A3B 2026-07-20)
# Binary: build-cuda-server/bin/llama-server (built 2026-05-09, b8271 CUDA sm_61)
# Do not use --mlock if n-cpu-moe changes
CUDA_VISIBLE_DEVICES=0 \
numactl --cpunodebind=0 --membind=0 \
/home/alex/llama.cpp/build-cuda-server/bin/llama-server \
  -m /home/alex/models/llm/moe/Qwen3.6-35B-A3B-UD-IQ4_XS.gguf \
  --n-gpu-layers 999 \
  --n-cpu-moe 16 \
  --no-mmap \
  --mlock \
  -c 8192 \
  --host 127.0.0.1 \
  --port 8082 \
  2>&1 | tee /home/alex/logs/routingneedle_server_$(date +%Y%m%d_%H%M%S).log
