#!/bin/bash

#wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
#chmod +x Miniconda3-latest-Linux-x86_64.sh
#./Miniconda3-latest-Linux-x86_64.sh -b
#conda install conda-forge::conda-ecosystem-user-package-isolation
# Restart the kernel

eval "$(conda shell.bash hook)"

conda env create --file environment.yml
source deactivate

conda create -n vllm python=3.9.19 -y
conda activate vllm
pip install vllm==0.5.5
cd convcodeworld
rm -rf bigcodebench
git clone https://github.com/stovecat/bigcodebench.git
cd bigcodebench

# Download sanitized_calibrated_samples
wget https://github.com/stovecat/convcodeworld/releases/download/v0.3.6/sanitized_calibrated_samples.tar.gz
tar -xzvf sanitized_calibrated_samples.tar.gz
rm sanitized_calibrated_samples.tar.gz

conda create -n bigcodebench python=3.9.19 -y
conda activate bigcodebench
export PYTHONPATH=$PYTHONPATH:$(pwd)
pip install -e .
pip install -r https://raw.githubusercontent.com/bigcode-project/bigcodebench/main/Requirements/requirements-eval.txt


conda create -n bigcodebenchgen python=3.9.19 -y
conda activate bigcodebenchgen
export PYTHONPATH=$PYTHONPATH:$(pwd)
pip install -e .
pip install -e .[generate]
pip install -U flash-attn
pip install mistralai
pip install stop_sequencer
#pip install rich
#pip install openai



