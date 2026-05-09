#!/bin/bash
# RoutingNeedle — WX9100 DeepSeek-V2-Lite server
# Gate 6 validated: no offload, c=8192, Green-band
# Do not add --n-cpu-moe — degrades gen from 92.93 to 24.6 tok/s
GGML_VK_VISIBLE_DEVICES=0 \
numactl --cpunodebind=1 --membind=1 \
/home/alex/llama.cpp/build/bin/llama-server \
  -m /home/alex/models/llm/moe/DeepSeek-V2-Lite.Q4_K_M.gguf \
  --n-gpu-layers 999 \
  --no-mmap \
  -c 8192 \
  --host 127.0.0.1 \
  --port 8081 \
  2>&1 | tee /home/alex/logs/routingneedle_server_deepseek_$(date +%Y%m%d_%H%M%S).log
