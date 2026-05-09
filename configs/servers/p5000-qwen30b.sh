#!/bin/bash
# RoutingNeedle — P5000 Qwen3-30B-A3B server
# Gate 8 validated: ncmoe=20, c=16384, Green-band
# Binary: build-cuda-server/bin/llama-server (built 2026-05-09, b8271 CUDA sm_61)
# Do not use --mlock if n-cpu-moe changes
CUDA_VISIBLE_DEVICES=0 \
numactl --cpunodebind=0 --membind=0 \
/home/alex/llama.cpp/build-cuda-server/bin/llama-server \
  -m /home/alex/models/llm/moe/Qwen3-30B-A3B-Q4_K_M.gguf \
  --n-gpu-layers 999 \
  --n-cpu-moe 20 \
  --no-mmap \
  --mlock \
  -c 16384 \
  --host 127.0.0.1 \
  --port 8080 \
  2>&1 | tee /home/alex/logs/routingneedle_server_$(date +%Y%m%d_%H%M%S).log
