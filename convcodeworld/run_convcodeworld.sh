#!/bin/bash
eval "$(conda shell.bash hook)"

CCW_VERSION=v0.3.6
MODEL_NAME=$1
BACKEND=$2
EF=$3
PARTIAL_TEST=$4
SUF=$5
USER_EXPERTISE=$6
DENYLIST=$7
DENYLIST_ITER=$8


#!/bin/bash
eval "$(conda shell.bash hook)"

model_name=${MODEL_NAME}
version=${CCW_VERSION}
backend=${BACKEND}
simulator_name=gpt-4o
simulator_backend=azure_openai
save_dir=results
denylist=${DENYLIST}
denylist_iter=${DENYLIST_ITER}

OPENAI_MODEL_LIST=("gpt-4o" "gpt-4-turbo-2024-04-09" "gpt-4-0613" "gpt-4o-mini" "gpt-35-turbo-0613" "gpt-35-turbo-instruct-0914")

if [[ " ${OPENAI_MODEL_LIST[@]} " =~ " ${model_name} " ]]; then
  gen_option=openai
else
  gen_option=vllm
fi


conda activate bigcodebench
cd bigcodebench
gen_path=sanitized_calibrated_samples/instruct/${model_name//\//--}--bigcodebench-instruct--${gen_option}-0-1-sanitized-calibrated.jsonl
./eval_single_dspy_result.sh $gen_path
cd ..

option="CF"
if [ $EF = 'true' ]; then
  option=${option}"_EF"
  if [ $PARTIAL_TEST = 'true' ]; then
    option=${option}"_UNIT"
  else
    option=${option}"_FULL"
  fi
fi
if [ $SUF = 'true' ]; then
  if [ $USER_EXPERTISE = "novice" ]; then
    option=${option}"_SNF"
  elif [ $USER_EXPERTISE = "expert" ]; then
    option=${option}"_SEF"
  fi
  if [ $model_name != $simulator_name ]; then
    option=${option}"_by_${simulator_name}"
  fi
fi

if [ -z "${denylist}" ]; then
  denylist="none"
  denylist_iter="none"
fi

for i in {1..10..1}
do
  conda activate ConvCodeWorld
  python run.py --model_name ${model_name} --use_generated_code true --generated_code_path bigcodebench/${gen_path} --compilation_feedback true --execution_feedback $EF --unit_test ${PARTIAL_TEST} --simulated_user_feedback ${SUF} --user_expertise ${USER_EXPERTISE}  --iteration $i --version $version  --save_dir $save_dir --backend $backend --simulator_backend $simulator_backend --denylist $denylist --denylist_iter ${denylist_iter}

  conda activate bigcodebench
  cd bigcodebench

  gen_path=../results/${version}/bigcodebench_${model_name//\//_}_${option}_ITER=${i}.jsonl
  if [ $i -eq 1 ]; then
    gen_path=../results/${version}/bigcodebench_${model_name//\//_}_${option}.jsonl
  fi
  ./eval_single_dspy_result.sh ${gen_path}
  cd ..
  conda deactivate
  conda deactivate
done