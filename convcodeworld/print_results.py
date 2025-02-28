import copy
import os
import argparse
from utils import load_json, load_jsonl, dump_json
from pot import compile_code
import numpy as np
from dataset import BigCodeBench
from prettytable import PrettyTable
from run import get_generation_results_fn, get_compact_gen_results_fn
from azure_open_ai import AZURE_OPENAI_MODEL_LIST

METHODS = ["w/ CF",
           "w/ CF EF (partial TC)",
           "w/ CF EF (full TC)",
           "w/ CF SNF",
           "w/ CF EF (partial TC) SNF",
           "w/ CF EF (full TC) SNF",
           "w/ CF SEF",
           "w/ CF EF (partial TC) SEF",
           "w/ CF EF (full TC) SEF"]


def get_keys(results):
    return sorted(results['eval'].keys(), key=lambda x: int(x.split('/')[-1]))


def get_code(results, key):
    return results['eval'][key][0]['solution']


def get_pass_fail(results, key):
    return results['eval'][key][0]['status']


def compilation_success(results, init_results):
    compilation_results = []
    for key in get_keys(results):
        code = get_code(results, key)
        init_code = get_code(init_results, key)
        if compile_code(code) is None or init_code is None:
            compilation_results.append(1.)
        else:
            compilation_results.append(0.)
    assert len(compilation_results) > 0
    return round(np.mean(compilation_results) * 100, 1)


def pass_at_1(results, init_results):
    pass_results = []
    for key in get_keys(results):
        if get_pass_fail(results, key) == 'pass' or get_pass_fail(init_results, key) == 'pass':
            pass_results.append(1.)
        else:
            pass_results.append(0.)
    assert len(pass_results) > 0
    return round(np.mean(pass_results) * 100, 1)


def static_pass_at_1_results(results):
    pass_results = []
    for key in get_keys(results):
        if get_pass_fail(results, key) == 'pass':
            pass_results.append(1.)
        else:
            pass_results.append(0.)
    assert len(pass_results) > 0
    return pass_results


def get_mrr(results_list, ref_results_list, option='live', compensate_init=False, exclude_init_solved=False, reported_result=None):
    mrr_results_dict = {}
    init_results = results_list[0]
    if option == 'live':
        for key in get_keys(init_results):
            if exclude_init_solved and get_pass_fail(init_results, key) == 'pass':
                continue
            mrr_results_dict[key] = 0
            for i in range(len(results_list)):
                results = results_list[i]
                if get_pass_fail(results, key) == 'pass':
                    mrr_results_dict[key] = 1 / (i + 1)
                    break
    elif option == 'static':
        ref_init_results = ref_results_list[0]
        for key in get_keys(init_results):
            if exclude_init_solved and get_pass_fail(init_results, key) == 'pass':
                continue
            mrr_results_dict[key] = 0
            if get_pass_fail(ref_init_results, key) == 'pass':
                mrr_results_dict[key] = 1.
                continue

            start_idx = 1
            if compensate_init:
                start_idx = 0
            for i in range(start_idx, len(results_list)):
                if i > 0:
                    prev_ref_results = ref_results_list[i - 1]
                    if get_pass_fail(prev_ref_results, key) == 'pass':
                        mrr_results_dict[key] = 1 / i
                        break
                results = results_list[i]
                if get_pass_fail(results, key) == 'pass':
                    mrr_results_dict[key] = 1 / (i + 1)
                    break
    if exclude_init_solved:
        print(f"{len(mrr_results_dict)}/{len(get_keys(init_results))}")
    return np.mean([mrr for mrr in mrr_results_dict.values()], axis=0)


def get_recall(results_list, ref_results_list, option='live', compensate_init=False, exclude_init_solved=False, reported_result=None):
    recall_results_dict = {}
    init_results = results_list[0]
    if option == 'live':
        for key in get_keys(init_results):
            if exclude_init_solved and get_pass_fail(init_results, key) == 'pass':
                continue
            recall_results_dict[key] = 0
            for i in range(len(results_list)):
                results = results_list[i]
                if get_pass_fail(results, key) == 'pass':
                    recall_results_dict[key] = 1.
                    break
    elif option == 'static':
        ref_init_results = ref_results_list[0]
        for key in get_keys(init_results):
            if exclude_init_solved and get_pass_fail(init_results, key) == 'pass':
                continue
            recall_results_dict[key] = 0
            if get_pass_fail(ref_init_results, key) == 'pass':
                recall_results_dict[key] = 1.
                continue

            start_idx = 0
            if compensate_init:
                start_idx = 0
            for i in range(start_idx, len(results_list)):
                if i > 0:
                    prev_ref_results = ref_results_list[i - 1]
                    if get_pass_fail(prev_ref_results, key) == 'pass':
                        recall_results_dict[key] = 1.
                        break
                results = results_list[i]
                if get_pass_fail(results, key) == 'pass':
                    recall_results_dict[key] = 1.
                    break
    if exclude_init_solved:
        print(f"{len(recall_results_dict)}/{len(get_keys(init_results))}")
    return np.mean([recall for recall in recall_results_dict.values()], axis=0)


def convert_eval_results_fn_to_gen_results_fn(eval_results_fn):
    return eval_results_fn.split("_eval_results.json")[0] + '.jsonl'


def get_data_point(dataset, key):
    for d in dataset.test:
        if d.task_id == key:
            return d
    return None


def get_configs(model_name, _save_dir, dataset_name, version, simulator_name, ref_model_name, option):
    configs = {}
    ref_configs = {}

    for CF in [False, True]:
        for EF in [False, True]:
            for SUF in [False, True]:
                for USER_EXPERTISE in ['novice', 'expert']:
                    for UNIT_TEST in [True, False]:
                        for CHEATING in [False, True]:
                            if CHEATING and USER_EXPERTISE != 'expert':
                                continue
                            key = ""
                            if CF:
                                key += "w/ CF"
                            else:
                                key = "w/o Feedback"
                            if EF:
                                key += " EF"
                                if UNIT_TEST:
                                    key += " (partial TC)"
                                else:
                                    key += " (full TC)"
                            if SUF:
                                if USER_EXPERTISE == 'novice':
                                    key += " SNF"
                                elif USER_EXPERTISE == 'expert':
                                    key += " SEF"
                                else:
                                    raise NotImplementedError
                                # if model_name != simulator_name:
                                #     key += f" ({simulator_name.split('/')[-1]})"
                                if CHEATING:
                                    key += " (Cheating)"

                            save_dir = _save_dir
                            if version is not None:
                                save_dir = os.path.join(save_dir, version)
                            if option == 'static':
                                save_folder = get_compact_gen_results_fn(dataset_name, ref_model_name, CF, EF, SUF,
                                                                         False, True,
                                                                         CHEATING, simulator_name, UNIT_TEST,
                                                                         USER_EXPERTISE, iter=1).replace('.jsonl', '')
                                save_dir = os.path.join(save_dir, 'static', save_folder)

                            configs[key] = {
                                "dataset_name": dataset_name,
                                "model_name": model_name,
                                "ref_model_name": ref_model_name,
                                "compilation_feedback": CF,
                                "execution_feedback": EF,
                                "simulated_user_feedback": SUF,
                                "raw_code_generation": False,
                                "use_generated_code": True,
                                "cheating": CHEATING,
                                "user_feedback_simulator_name": simulator_name,
                                "unit_test": UNIT_TEST,
                                "user_expertise": USER_EXPERTISE,
                                "save_dir": save_dir
                            }
                            ref_configs[key] = {
                                "dataset_name": dataset_name,
                                "model_name": ref_model_name,
                                "ref_model_name": None,
                                "compilation_feedback": CF,
                                "execution_feedback": EF,
                                "simulated_user_feedback": SUF,
                                "raw_code_generation": False,
                                "use_generated_code": True,
                                "cheating": CHEATING,
                                "user_feedback_simulator_name": simulator_name,
                                "unit_test": UNIT_TEST,
                                "user_expertise": USER_EXPERTISE,
                                "save_dir": save_dir.split('static')[0]
                            }
    return configs, ref_configs


def get_results_dict(model_name, reported_path, ref_reported_path, configs, ref_configs, max_iteration, option, compensate_init, exclude_init_solved=False):
    mrr_results_dict, recall_results_dict = {}, {}
    eval_results_dict, ref_eval_results_dict = {}, {}

    for method, config in configs.items():
        ref_config = ref_configs[method]
        if model_name in AZURE_OPENAI_MODEL_LIST:
            if method.lower() in ["official", "reported"]:
                continue
            elif method == "Direct Generation (i.e. model.generate from BigCodeBench Repo)":
                method = "Direct Generation"

        eval_results_list = []
        ref_eval_results_list = []
        for iteration in range(1, max_iteration + 1):
            if iteration > 1:
                config['iter'] = iteration
                ref_config['iter'] = iteration
            if iteration == 1 and method.lower() in ["official", "reported"]:
                continue

            save_dir = config['save_dir']
            tmp_config = {k: v for k, v in config.items() if k != 'ref_model_name' and k != 'save_dir'}
            tmp_config['iter'] = iteration
            gen_fn = get_compact_gen_results_fn(**tmp_config)
            gen_path = os.path.join(save_dir, gen_fn)
            eval_path = gen_path.replace('.jsonl', '_eval_results.json')

            if option == 'static':
                ref_save_dir = ref_config['save_dir']
                tmp_ref_config = {k: v for k, v in ref_config.items() if k != 'ref_model_name' and k != 'save_dir'}
                tmp_ref_config['iter'] = iteration
                ref_gen_fn = get_compact_gen_results_fn(**tmp_ref_config)
                ref_gen_path = os.path.join(ref_save_dir, ref_gen_fn)
                ref_eval_path = ref_gen_path.replace('.jsonl', '_eval_results.json')

            if iteration == 1:
                eval_results_list.append(load_json(reported_path))
                if option == 'static':
                    ref_eval_results_list.append(load_json(ref_reported_path))

            if os.path.exists(eval_path):
                try:
                    eval_results_list.append(load_json(eval_path))
                    if option == 'static':
                        ref_eval_results_list.append(load_json(ref_eval_path))
                except Exception as e:
                    print(e)
                    break

        if len(eval_results_list) == max_iteration + 1:
            mrr_results_dict[method] = get_mrr(eval_results_list, ref_eval_results_list, option=option,
                                               compensate_init=compensate_init, exclude_init_solved=exclude_init_solved)
            recall_results_dict[method] = get_recall(eval_results_list, ref_eval_results_list, option=option,
                                                     compensate_init=compensate_init, exclude_init_solved=exclude_init_solved)
            eval_results_dict[method] = eval_results_list
            ref_eval_results_dict[method] = ref_eval_results_list

    return mrr_results_dict, recall_results_dict, eval_results_dict, ref_eval_results_dict


def print_per_turn_results(model_name, version, simulator_name, reported_path, ref_model_name, ref_reported_path, option, max_iteration,
                           eval_results_dict, ref_eval_results_dict):
    methods = copy.deepcopy(METHODS)
    # if model_name != simulator_name:
    #     methods = [k + f' ({simulator_name})' if 'SNF' in k or 'SEF' in k else k for k in methods]
    if option == 'static':
        methods = [k for k in methods if ('SNF' in k and 'EF' in k) or 'SEF' in k]

    init_results = load_json(reported_path)
    if option == 'static':
        ref_init_results = load_json(ref_reported_path)
    rows = []
    for iteration in range(0, max_iteration + 1):
        row = []
        if option == 'static' and iteration == 0:
            continue
        row.append(iteration)

        for method in methods:
            if method in ['w/ CF', 'w/ CF SNF']:
                if option == 'static':
                    pass
                elif method in eval_results_dict.keys():
                    results = eval_results_dict[method][iteration]
                    row.append(pass_at_1(results, init_results))
                else:
                    assert compilation_success(init_results, init_results) == 100.0, f"{compilation_success(init_results, init_results)}"
                    row.append(pass_at_1(init_results, init_results))
                continue
            if method not in eval_results_dict.keys() or iteration >= len(eval_results_dict[method]):
                row.append('')
                continue
            results = eval_results_dict[method][iteration]
            if option == 'live':
                row.append(pass_at_1(results, init_results))
            elif option == 'static':
                ref_results = ref_eval_results_dict[method]
                row.append(pass_at_1(results, ref_init_results))
        rows.append(row)

    table = PrettyTable()
    table.field_names = ["Turn"] + methods
    table.align = "c"
    table.add_rows(rows)
    print(table)
    table_caption = f"Table 1. Pass@1 results of {model_name} on ConvCodeWorld for each turn."
    if option == 'static':
        table_caption = f"Table 1. Pass@1 results of {model_name} on ConvCodeBench for each turn (ref. model: {ref_model_name})."
    # if version is not None:
    #     table_caption += f" ({version})"
    table_caption += "\n - CF: Compilation Feedback\n - EF: Execution Feedback\n - partial|full TC: test cases with partial|full Test Coverage \n - SNF: Simulated Novice Feedback\n - SEF: Simulated Expert Feedback"
    print(table_caption)
    print()

    return methods, rows


def print_mrr_recall(model_name, simulator_name, ref_model_name, option, mrr_results_dict, recall_results_dict, reported_path):
    methods = copy.deepcopy(METHODS)
    # if model_name != simulator_name:
    #     methods = [k + f' ({simulator_name})' if 'SNF' in k or 'SEF' in k else k for k in methods]
    if option == 'static':
        methods = [k for k in methods if ('SNF' in k and 'EF' in k) or 'SEF' in k]

    init_results = load_json(reported_path)
    headers = []
    mrr_rows = ["MRR"]
    recall_rows = ["Recall"]
    for method in methods:
        if method in ['w/ CF', 'w/ CF SNF']:
            if option == 'static':
                continue
            elif method not in mrr_results_dict.keys():
                assert compilation_success(init_results, init_results) == 100.0, f"{compilation_success(init_results, init_results)}"
                headers.append(method)
                mrr_rows.append(pass_at_1(init_results, init_results))
                recall_rows.append(pass_at_1(init_results, init_results))
                continue
        if method not in mrr_results_dict.keys():
            continue
        headers.append(method)
        mrr_rows.append(str(round(mrr_results_dict[method] * 100, 1)))
        recall_rows.append(str(round(recall_results_dict[method] * 100, 1)))

    table = PrettyTable()
    table.field_names = ["Metrics"] + headers
    table.align = "c"
    table.add_rows([mrr_rows, recall_rows])
    print(table)
    table_caption = f"Table 2. MRR and Recall results of {model_name} on ConvCodeWorld."
    if option == 'static':
        table_caption = f"Table 2. MRR and Recall results of {model_name} on ConvCodeBench (ref. model: {ref_model_name})."
    print(table_caption)
    print()


def main(model_name, _save_dir, dataset_name, reported_path, version=None, simulator_name=None,
         ref_model_name=None, ref_reported_path=None, max_iteration=10, option="all", compensate_init=False, exclude_init_solved=False):
    assert option in ["live", "static", "all"]
    if option == 'all':
        option_list = ['live', 'static']
    else:
        option_list = [option]

    for option in option_list:
        configs, ref_configs = get_configs(model_name, _save_dir, dataset_name, version, simulator_name, ref_model_name,
                                           option)

        mrr_results_dict, recall_results_dict, eval_results_dict, ref_eval_results_dict = get_results_dict(model_name,
                                                                                                           reported_path,
                                                                                                           ref_reported_path,
                                                                                                           configs,
                                                                                                           ref_configs,
                                                                                                           max_iteration,
                                                                                                           option,
                                                                                                           compensate_init,
                                                                                                           exclude_init_solved)

        print_per_turn_results(model_name, version, simulator_name, reported_path, ref_model_name, ref_reported_path, option,
                               max_iteration, eval_results_dict, ref_eval_results_dict)

        print_mrr_recall(model_name, simulator_name, ref_model_name, option, mrr_results_dict, recall_results_dict, reported_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default='deepseek-ai/deepseek-coder-6.7b-instruct')
    parser.add_argument("--save_dir", type=str, default='results')
    parser.add_argument("--dataset_name", type=str, default='bigcodebench')
    parser.add_argument("--version", type=str, default='v0.3.6')
    parser.add_argument("--max_iteration", type=int, default=10,
                        help="Number of user feedback iterations.")
    parser.add_argument("--simulator_name", type=str, default='gpt-4o')
    parser.add_argument("--ref_model_name", type=str, default='codellama/CodeLlama-7b-Instruct-hf')
    parser.add_argument("--option", type=str, default='all')
    parser.add_argument("--compensate_init", type=lambda x: (str(x).lower() == 'true'), default=True)
    parser.add_argument("--exclude_init_solved", type=lambda x: (str(x).lower() == 'true'), default=False)
    

    args = parser.parse_args()

    if args.model_name in AZURE_OPENAI_MODEL_LIST:
        source = 'openai'
    else:
        source = 'openai'
    if args.ref_model_name in AZURE_OPENAI_MODEL_LIST:
        ref_source = 'openai'
    else:
        ref_source = 'openai'

    reported_path = f"bigcodebench/sanitized_calibrated_samples/instruct/{args.model_name.replace('/', '--')}--bigcodebench-instruct--{source}-0.2-1-sanitized-calibrated_eval_results.json"
    ref_reported_path = f"bigcodebench/sanitized_calibrated_samples/instruct/{args.ref_model_name.replace('/', '--')}--bigcodebench-instruct--{ref_source}-0.2-1-sanitized-calibrated_eval_results.json"

    main(args.model_name,
         args.save_dir,
         args.dataset_name,
         reported_path,
         args.version,
         args.simulator_name,
         args.ref_model_name,
         ref_reported_path,
         args.max_iteration,
         args.option,
         args.compensate_init,
         args.exclude_init_solved)
