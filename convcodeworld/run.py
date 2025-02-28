import os
import dspy
import json
from dataset import BigCodeBench
from pot import ProgramOfThought
from tqdm import tqdm
import argparse
from azure_open_ai import get_azure_lm, get_openai_lm, AZURE_OPENAI_MODEL_LIST
import subprocess
from utils import load_jsonl, dump_jsonl

def run_execution(command, run_dir="bigcodebench", env_name="bigcodebench"):
    command = "\n".join([f"cd {run_dir}",
                         f"\nconda run -n {env_name} {command}"
                         ])
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        print(f"Error: {stderr.decode('utf-8')}")
    else:
        print(f"Output: {stdout.decode('utf-8')}")


def get_generation_results_fn(dataset_name, model_name, compilation_feedback, execution_feedback, simulated_user_feedback,
                              raw_code_generation, use_generated_code, cheating, user_feedback_simulator_name, unit_test,
                              user_expertise, iter):

    fn = f"{dataset_name}_{model_name.replace('/','_')}_{compilation_feedback=}_{execution_feedback=}_{simulated_user_feedback=}_{raw_code_generation=}_{use_generated_code=}"
    if simulated_user_feedback and cheating:
        fn += "_cheating=True"
    if simulated_user_feedback and not cheating and model_name != user_feedback_simulator_name:
        fn += f"_user_feedback_simulator_name={user_feedback_simulator_name.replace('/','_')}"
    if execution_feedback and unit_test:
        fn += f"_unit_test=True"
    assert not simulated_user_feedback or cheating or user_expertise in ["novice", "expert"]
    if simulated_user_feedback and user_expertise not in ["expert", None]:
        fn += "_"+user_expertise
    if iter > 1:
        fn += f"_{iter=}"
    fn += ".jsonl"

    return fn

def get_compact_gen_results_fn(dataset_name, model_name, compilation_feedback, execution_feedback, simulated_user_feedback,
                              raw_code_generation, use_generated_code, cheating, user_feedback_simulator_name, unit_test,
                              user_expertise, iter):
    if raw_code_generation or not use_generated_code:
        return None

    fn = f"{dataset_name}_{model_name.replace('/','_')}"
    if compilation_feedback:
        fn += "_CF"
    if execution_feedback:
        fn += '_EF'
        if unit_test:
            fn += '_UNIT'
        else:
            fn += '_FULL'
    if simulated_user_feedback:
        if cheating:
            fn += '_CHEATED'
        else:
            if user_expertise == 'expert':
                fn += '_SEF'
            elif user_expertise == 'novice':
                fn += '_SNF'
            if model_name != user_feedback_simulator_name:
                fn += f"_by_{user_feedback_simulator_name.replace('/','_')}"
    if iter > 1:
        fn += f"_ITER={iter}"
    fn += ".jsonl"

    return fn

def commentize_code(path, task_id):
    prefix = "#### ALREADY COMMENTIZED ####\n"
    data = load_jsonl(path)
    code = None
    for d in data:
        if d['task_id'] == task_id:
            code = d['solution']
    assert code is not None

    if code.split('\n')[0] == prefix:
        return code
    return prefix+ "\n".join([f"# {l}" for l in code.split('\n')])


def apply_code_to_jsonl(path, task_id, code):
    data = load_jsonl(path)
    updated_data = []
    for d in data:
        tmp_dict = {key: val for key, val in d.items()}
        if d['task_id'] == task_id:
            tmp_dict['solution'] = code
        updated_data.append(tmp_dict)
    dump_jsonl(updated_data, path)

def get_deny_flag(task_id, iteration, denylist, denylist_iter):
    for deny_id, deny_iter in zip(denylist, denylist_iter):
        if task_id == deny_id and iteration >= deny_iter:
            return True, iteration == deny_iter
    else:
        return False, False


def run(lm, fn, dataset, generate_answer_signature,
        save_dir, dataset_name, compilation_feedback,
        execution_feedback, simulated_user_feedback,
         raw_code_generation, use_generated_code,
        generated_code_path, execution_results_path,
        cheating, user_feedback_simulator, user_expertise,
        unit_test, iteration, generated_feedback_path,
        denylist, denylist_iter):
    results = {}
    if os.path.exists(f"{save_dir}/{fn}"):
        with open(f"{save_dir}/{fn}", 'r') as fp:
            for l in fp.readlines():
                d = json.loads(l)
                results[d['task_id']] = d

    dataset_dict = {v.task_id: v for v in dataset.test}

    for test_example in tqdm(dataset.test):
        task_id = test_example.task_id
        deny_flag, is_deny_iter_now = get_deny_flag(task_id, iteration, denylist, denylist_iter)
        if task_id in results.keys():
            if deny_flag:
                pass
            else:
                print(f"{task_id} is already generated in {fn}")
                continue
        
        if deny_flag:
            print(f"The lastly generated code of {task_id} ")
            if is_deny_iter_now:
                commentized_code = commentize_code(f"{save_dir}/{fn}", task_id)
            else:
                commentized_code = commentize_code(generated_code_path, task_id)
                
            result = {'task_id': test_example.task_id,
                      'solution': commentized_code,
                      'compilation_feedback': None,
                      'execution_feedback': None,
                      'user_feedback': None,
                      'log': "# CRITICAL ERROR WHILE EXECUTING THE GENERATED CODE",
                      'iteration': iteration,}
            
            if is_deny_iter_now:
                apply_code_to_jsonl(f"{save_dir}/{fn}", task_id, commentized_code)
            else:
                with open(f"{save_dir}/{fn}", 'a+') as fp:
                    json.dump(result, fp)
                    fp.write('\n')
            continue


        # from pot import ProgramOfThought
        # Pass signature to ProgramOfThought Module
        pot = ProgramOfThought(generate_answer_signature,
                               allow_all_imports=True,
                               compilation_feedback=compilation_feedback,
                               execution_feedback=execution_feedback,
                               simulated_user_feedback=simulated_user_feedback,
                               raw_generate=raw_code_generation,
                               use_generated_code=use_generated_code,
                               generated_code_path=generated_code_path,
                               execution_results_path=execution_results_path,
                               cheating=cheating,
                               user_feedback_simulator=user_feedback_simulator,
                               user_expertise=user_expertise,
                               unit_test=unit_test,
                               iteration=iteration,
                               dataset=dataset_dict,
                               generated_feedback_path=generated_feedback_path)

        # Call the ProgramOfThought module on a particular input
        _result = pot(input=test_example.instruct_prompt, task_id=task_id)

        # print(lm.inspect_history(n=4))

        # print(f"Input: {test_example.instruct_prompt}")
        # print()
        #

        if dataset_name == 'bigcodebench':
            header = test_example.code_prompt.split('def task_func')[0]
            _result['final_generated_code'] = header + _result['final_generated_code']

        log = None
        try:
            log = lm.inspect_history(n=1)
        except AttributeError as e:
            print(e)


        result = {'task_id': test_example.task_id,
                  'solution': _result['final_generated_code'],
                  'compilation_feedback': _result['compilation_feedback'],
                  'execution_feedback': _result['execution_feedback'],
                  'user_feedback': _result['user_feedback'],
                  'log': log,
                  'iteration': _result['iteration'],}

        print(f"[TASK_ID={result['task_id']}]")
        print(f"[CODE]:\n{result['solution']}")
        print()
        print(f"Compilation Feedback: {result['compilation_feedback']}")
        print(f"Execution Feedback: {result['execution_feedback']}")
        print(f"(Simulated) User Feedback: {result['user_feedback']}")
        print()
        with open(f"{save_dir}/{fn}", 'a+') as fp:
            json.dump(result, fp)
            fp.write('\n')



def main(model_name, save_dir, dataset_name, compilation_feedback, execution_feedback, simulated_user_feedback,
         raw_code_generation, use_generated_code, generated_code_path, cheating, user_feedback_simulator_name,
         user_expertise, unit_test, iteration, version, option, ref_model_name, ref_generated_code_path, backend, simulator_backend,
         denylist, denylist_iter, port_number):

    if backend == 'openai':
        lm = get_openai_lm(model_name)
    elif backend == 'azure_openai':
        assert model_name in AZURE_OPENAI_MODEL_LIST
        lm = get_azure_lm(model_name)
    elif backend == 'vllm':
        lm = dspy.HFClientVLLM(model=model_name, port=port_number, url="http://localhost", max_tokens=2048, stop=["\n\n---\n\n"])
    else:
        raise NotImplementedError

    if user_feedback_simulator_name in [None, model_name]:
        user_feedback_simulator = lm
    elif simulator_backend == 'openai':
        user_feedback_simulator = get_openai_lm(user_feedback_simulator_name)
    elif simulator_backend == 'azure_openai':
        assert user_feedback_simulator_name in AZURE_OPENAI_MODEL_LIST
        user_feedback_simulator = get_azure_lm(user_feedback_simulator_name)
    elif simulator_backend == 'vllm':
        user_feedback_simulator = dspy.HFClientVLLM(model=user_feedback_simulator_name, port=port_number, url="http://localhost",
                                                    max_tokens=2048, stop=["\n\n---\n\n"])
    else:
        raise NotImplementedError

    dspy.settings.configure(lm=lm)

    if dataset_name == 'bigcodebench':
        dataset = BigCodeBench()
    else:
        raise NotImplementedError

    generate_answer_signature = dspy.Signature("input -> output")

    if version is not None:
        save_dir = os.path.join(save_dir, version)

    execution_results_path = None
    generated_feedback_path = None

    if option == 'live':
        # if execution_feedback:
        assert use_generated_code, "Currently we only support use_generated_code=True"
        execution_results_path = generated_code_path.replace('.jsonl', '_eval_results.json')

        if iteration > 1:
            prev_fn = get_compact_gen_results_fn(dataset_name, model_name, compilation_feedback, execution_feedback, simulated_user_feedback,
                                                raw_code_generation, use_generated_code, cheating, user_feedback_simulator_name, unit_test,
                                                user_expertise, iteration-1)
            generated_code_path = f"{save_dir}/{prev_fn}"
            execution_results_path = generated_code_path.replace('.jsonl', '_eval_results.json')
            assert os.path.exists(generated_code_path), "{} does not exist".format(generated_code_path)
            assert os.path.exists(execution_results_path), "{} does not exist".format(execution_results_path)
    elif option == 'static':
        if iteration == 1:
            generated_code_path = ref_generated_code_path
        elif iteration > 1:
            prev_fn = get_compact_gen_results_fn(dataset_name, ref_model_name, compilation_feedback, execution_feedback,
                                                 simulated_user_feedback,
                                                 raw_code_generation, use_generated_code, cheating,
                                                 user_feedback_simulator_name, unit_test,
                                                 user_expertise, iteration - 1)
            generated_code_path = f"{save_dir}/{prev_fn}"
        else:
            raise NotImplementedError
        assert os.path.exists(generated_code_path), "{} does not exist".format(generated_code_path)

        assert use_generated_code, "Currently execution feedback only supports when use_generated_code=True"
        execution_results_path = generated_code_path.replace('.jsonl', '_eval_results.json')

        if simulated_user_feedback:
            generated_feedback_fn = get_compact_gen_results_fn(dataset_name, ref_model_name, compilation_feedback, execution_feedback,
                                                               simulated_user_feedback,
                                                               raw_code_generation, use_generated_code, cheating,
                                                               user_feedback_simulator_name, unit_test,
                                                               user_expertise, iteration)
            generated_feedback_path = f"{save_dir}/{generated_feedback_fn}"
            assert os.path.exists(generated_feedback_path), "{} does not exist".format(generated_feedback_path)

        save_folder = get_compact_gen_results_fn(dataset_name, ref_model_name, compilation_feedback, execution_feedback,
                                                 simulated_user_feedback,
                                                 raw_code_generation, use_generated_code, cheating,
                                                 user_feedback_simulator_name, unit_test,
                                                 user_expertise, iter=1).replace('.jsonl', '')
        save_dir = f"{save_dir}/static/{save_folder}"

        print(f"{generated_code_path=}")
        print(f"{execution_results_path=}")
        print(f"{generated_feedback_path=}")
        print(f"{save_dir=}")
        # assert 1 == 2
    else:
        raise NotImplementedError
    fn = get_compact_gen_results_fn(dataset_name, model_name, compilation_feedback, execution_feedback, simulated_user_feedback,
                                   raw_code_generation, use_generated_code, cheating, user_feedback_simulator_name, unit_test,
                                   user_expertise, iteration)

    os.makedirs(save_dir, exist_ok=True)

    # for iter in range(1, +1):

    # fn = f"{dataset_name}_{model_name.replace('/','_')}_{compilation_feedback=}_{execution_feedback=}_{simulated_user_feedback=}_{raw_code_generation=}_{use_generated_code=}"
    # if simulated_user_feedback and cheating:
    #     fn += "_cheating=True"
    # if simulated_user_feedback and model_name != user_feedback_simulator_name:
    #     fn += f"_user_feedback_simulator_name={user_feedback_simulator_name}"
    # if execution_feedback and unit_test:
    #     fn += f"_unit_test=True"
    # if iter > 1:
    #     fn += f"_{iter=}"
    # fn += ".jsonl"

    run(lm, fn, dataset, generate_answer_signature,
        save_dir, dataset_name, compilation_feedback,
        execution_feedback, simulated_user_feedback,
        raw_code_generation, use_generated_code,
        generated_code_path, execution_results_path,
        cheating, user_feedback_simulator, user_expertise,
        unit_test, iteration, generated_feedback_path,
        denylist, denylist_iter)

    # run_execution(command=f"./eval_single_dspy_result.sh ../{save_dir}/{fn}", run_dir='bigcodebench', env_name='bigcodebench')

    # if execution_feedback:
    #     execution_results_path = f"{save_dir}/{fn.replace('.jsonl', '_eval_results.json')}"





if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default='deepseek-ai/deepseek-coder-6.7b-instruct')
    parser.add_argument("--save_dir", type=str, default='results')
    parser.add_argument("--dataset_name", type=str, default='bigcodebench')
    parser.add_argument("--compilation_feedback", type=lambda x: (str(x).lower() == 'true'), default=False)
    parser.add_argument("--execution_feedback", type=lambda x: (str(x).lower() == 'true'), default=False)
    parser.add_argument("--simulated_user_feedback", type=lambda x: (str(x).lower() == 'true'), default=False)
    parser.add_argument("--raw_code_generation", type=lambda x: (str(x).lower() == 'true'), default=False)
    parser.add_argument("--use_generated_code", type=lambda x: (str(x).lower() == 'true'), default=False,
                        help="Load already generated code and use as initial code inputs. \
                              Direct completion without instructions should be done in this way.")
    parser.add_argument("--generated_code_path", type=str,
                        default='/notebooks/snowcoder/evaluation/ConvCodeBench/bigcodebench/deepseek-ai--deepseek-coder-6.7b-instruct--bigcodebench-instruct--vllm-0-1-sanitized-calibrated.jsonl')
    parser.add_argument("--cheating", type=lambda x: (str(x).lower() == 'true'), default=False,
                        help="Directly give ground truth code as simulated user feedback.")
    parser.add_argument("--iteration", type=int, default=1,
                        help="Number of user feedback iterations.")
    parser.add_argument("--user_feedback_simulator_name", type=str, default='gpt-4o',
                        help="User feedback simulator name.")
    parser.add_argument("--unit_test", type=lambda x: (str(x).lower() == 'true'), default=False)
    parser.add_argument("--user_expertise", type=str, default='expert')
    parser.add_argument("--version", type=str, default=None)
    parser.add_argument("--option", type=str, default='live')
    parser.add_argument("--ref_model_name", type=str, default=None)
    parser.add_argument("--ref_generated_code_path", type=str, default=None)
    parser.add_argument("--backend", type=str, default='vllm',
                        help="Backend types: vllm|openai|azure_openai")
    parser.add_argument("--simulator_backend", type=str, default='openai',
                        help="Backend types of uer simulator: vllm|openai|azure_openai")
    parser.add_argument("--denylist", type=str, default=None,
                        help="A list of task ids to skip the experiment. Split by commas. \
                              Use this if the generated code of that id incurs undesirable effects such as termination of the experiment, damage to the environment, etc.")
    parser.add_argument("--denylist_iter", type=str, default=None,
                        help="A list of iteration numbers for denylist to skip the experiment. Split by commas.")
    parser.add_argument("--port_number", type=int, default=7777,
                        help="Port number for vllm")

    args = parser.parse_args()

    assert args.option in ['live', 'static']
    if args.option == 'static':
        assert args.ref_model_name is not None

    if args.denylist is not None and args.denylist.lower() != 'none':
        args.denylist = args.denylist.split(',')
        args.denylist_iter = [int(d_iter) for d_iter in args.denylist_iter.split(',')]
        tmp_indices = [i for i, d_iter in enumerate(args.denylist_iter) if d_iter <= args.iteration]
        args.denylist = [task_id for i, task_id in enumerate(args.denylist) if i in tmp_indices]
        args.denylist_iter = [d_iter for i, d_iter in enumerate(args.denylist_iter) if i in tmp_indices]
    else:
        args.denylist = []
        args.denylist_iter = []
    print(args)

    main(**args.__dict__)

