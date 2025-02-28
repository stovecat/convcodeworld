#!/bin/bash
eval "$(conda shell.bash hook)"

ENV_CCB_YML="s3://ml-dev-sfc-or-dev-misc1-k8s/research/2024/hhan/ConvCodeBench/environment.yml"
ENV_BCB_YML="s3://ml-dev-sfc-or-dev-misc1-k8s/research/2024/hhan/ConvCodeBench/bigcodebench/environment.yml"

source deactivate
aws s3 cp ${ENV_CCB_YML} environment.yml

conda env create --file environment.yml
source deactivate

aws s3 cp ${ENV_BCB_YML} bcb_environment.yml
conda env create --file bcb_environment.yml

conda create -n vllm python=3.9.19 -y
conda activate vllm


