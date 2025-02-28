#!/bin/bash
eval "$(conda shell.bash hook)"

model_name="deepseek-ai/DeepSeek-R1-Distill-Llama-70B"
version=${CCB_VERSION}
backend=vllm
simulator_name=gpt-4o
simulator_backend=azure_openai
denylist=${DENYLIST}
denylist_iter=${DENYLIST_ITER}
port_number=7778
EF=true
UNIT_TEST=true
USER_EXPERTISE=expert

OPENAI_MODEL_LIST=("deepseek-ai/DeepSeek-R1-Distill-Llama-70B" "gpt-4o" "gpt-4-turbo-2024-04-09" "gpt-4-0613" "gpt-4o-mini" "gpt-35-turbo-0613" "gpt-35-turbo-instruct-0914")

if [[ " ${OPENAI_MODEL_LIST[@]} " =~ " ${model_name} " ]]; then
  gen_option=openai
else
  gen_option=vllm
fi


source /home/yak/miniconda/bin/activate bigcodebench
cd bigcodebench
gen_path=sanitized_calibrated_samples/instruct/${model_name//\//--}--bigcodebench-instruct--${gen_option}-0.2-1-sanitized-calibrated.jsonl
./eval_single_dspy_result.sh $gen_path
cd ..

option="CF"
if [ $EF = 'true' ]; then
  option=${option}"_EF"
  if [ $UNIT_TEST = 'true' ]; then
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

mkdir -p results/${version}
aws s3 cp s3://ml-dev-sfc-or-dev-misc1-k8s/research/2024/hhan/ConvCodeBench/results/${version}/ results/${version}/ --recursive --exclude "*" --include "bigcodebench_${model_name//\//_}_${option}*"

for i in {1..10..1}
do
  source /home/yak/miniconda/bin/activate ConvCodeBenchJOB
  #python run.py --model_name ${model_name} --use_generated_code true --generated_code_path bigcodebench/${gen_path} --compilation_feedback true --execution_feedback true --simulated_user_feedback true --unit_test true  --iteration $i --version $version
  python run.py --model_name ${model_name} --use_generated_code true --generated_code_path bigcodebench/${gen_path} --compilation_feedback true --execution_feedback $EF --unit_test ${UNIT_TEST} --simulated_user_feedback ${SUF} --user_expertise ${USER_EXPERTISE}  --iteration $i --version $version --denylist $denylist --denylist_iter ${denylist_iter} --backend $backend --user_feedback_simulator_name $simulator_name --simulator_backend $simulator_backend --port_number $port_number

  source /home/yak/miniconda/bin/activate bigcodebench
  cd bigcodebench

#  gen_path=../results/v0.3.6/bigcodebench_${model_name//\//_}_CF_EF_UNIT_SEF_by_${simulator_name}_ITER=${i}.jsonl
#  if [ $i -eq 1 ]; then
#    gen_path=../results/v0.3.6/bigcodebench_${model_name//\//_}_CF_EF_UNIT_SEF_by_${simulator_name}.jsonl
#  fi
  gen_path=../results/${version}/bigcodebench_${model_name//\//_}_${option}_ITER=${i}.jsonl
  if [ $i -eq 1 ]; then
    gen_path=../results/${version}/bigcodebench_${model_name//\//_}_${option}.jsonl
  fi
  ./eval_single_dspy_result.sh ${gen_path}
  cd ..
  source /home/yak/miniconda/bin/deactivate
  source /home/yak/miniconda/bin/deactivate
  aws s3 sync results s3://ml-dev-sfc-or-dev-misc1-k8s/research/2024/hhan/ConvCodeBench/results
done
