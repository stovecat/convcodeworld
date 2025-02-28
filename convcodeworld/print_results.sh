#!/bin/bash
eval "$(conda shell.bash hook)"
conda activate ConvCodeBenchJOB

OPTION=$1
MODEL_NAME=$2
REF_MODEL_NAME=$3
SAVE_DIR=$4

if [ -z "${REF_MODEL_NAME}" ]; then
  REF_MODEL_NAME="codellama/CodeLlama-7b-Instruct-hf"
fi
if [ -z "${SAVE_DIR}" ]; then
  SAVE_DIR="results"
fi


python print_results.py --option $OPTION --model_name $MODEL_NAME --save_dir $SAVE_DIR --ref_model_name $REF_MODEL_NAME --max_iteration 1
