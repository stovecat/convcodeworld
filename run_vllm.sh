#!/bin/bash

MODEL_NAME=$1

eval "$(conda shell.bash hook)"
conda activate vllm
# If you want to use quantization, please include: --quantization="fp8"
# If you want to use n gpus, please include: --tensor-parallel-size n
python -m vllm.entrypoints.openai.api_server --model ${MODEL_NAME} --port 7777 --trust-remote-code --max-model-len 8000 --dtype bfloat16
