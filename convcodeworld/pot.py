import os
import re
import copy
import dspy
from dspy.signatures.signature import ensure_signature

from dspy.primitives.program import Module
from utils import load_jsonl, load_json
import traceback
from dataset import BigCodeBench
from extract_methods import extract_methods_from_class
from user_feedback_examples import (EXPERT_FEEDBACK_EXAMPLE, NOVICE_FEEDBACK_EXAMPLE,
                                    EXECUTION_EXPERT_FEEDBACK_EXAMPLE, EXECUTION_NOVICE_FEEDBACK_EXAMPLE)

NO_SYNTAX_ERRORS = 'No syntax errors'
PASSED_ALL_TEST_RUNS = 'Passed all test runs'
NUM_UNIT_TESTS = 3
MAX_TOKEN_LEN = 16000


def compile_code(code):
    try:
        compile(code, 'tmp.py', mode='exec')
    except Exception as e:
        return traceback.format_exc()
    return None


class ProgramOfThought(Module):
    def __init__(self, signature, max_iters=3, import_white_list=None, allow_all_imports=True, language='Python',
                 compilation_feedback=False, execution_feedback=False, simulated_user_feedback=False, raw_generate=False,
                 use_generated_code=False, generated_code_path=None, execution_results_path=None, cheating=False,
                 user_feedback_simulator=None, user_expertise='expert', unit_test=False, iteration=1, dataset=None,
                 generated_feedback_path=None):
        super().__init__()
        self.signature = signature = ensure_signature(signature)
        self.language = language
        self.code_template = None
        if self.language == 'Python':
            self.code_template = 'python code'
        elif self.language == 'SQL':
            self.code_template = 'sql query'
        else:
            raise NotImplementedError

        self.max_iters = max_iters
        self.import_white_list = import_white_list
        self.allow_all_imports = allow_all_imports
        self.compilation_feedback = compilation_feedback
        self.execution_feedback = execution_feedback
        self.simulated_user_feedback = simulated_user_feedback
        self.raw_generate = raw_generate
        self.use_generated_code = use_generated_code
        self.generated_code_path = generated_code_path
        self.execution_results_path = execution_results_path
        self.cheating = cheating
        self.user_feedback_simulator = user_feedback_simulator
        self.user_expertise = user_expertise
        self.unit_test = unit_test
        self.iteration = iteration

        assert (self.raw_generate and not self.use_generated_code) or \
               (not self.raw_generate and self.use_generated_code) or \
               (not self.raw_generate and not self.use_generated_code), \
               "raw_generate is unavailable if use_generated_code is True"

        self.dataset = dataset
        self.generated_code_dict = None
        if self.use_generated_code or self.iteration > 1:
            assert os.path.exists(self.generated_code_path), "generated_code_path does not exist"
            self.generated_code_dict = {v['task_id']: v['solution'] for v in load_jsonl(self.generated_code_path)}
        self.execution_results_dict = None
        if self.execution_results_path is not None:
            assert os.path.exists(self.execution_results_path), "execution_results_path does not exist"
            self.execution_results_dict = {k: {'code': v[0]['solution'],
                                               'status': v[0]['status'],
                                               'execution_feedback': v[0]['details']}
                                           for k, v in load_json(self.execution_results_path)['eval'].items()}
        self.generated_feedback_dict = None
        if generated_feedback_path is not None:
            self.generated_feedback_dict = {v['task_id']: {'compilation_feedback': v['compilation_feedback'],
                                                           'execution_feedback': v['execution_feedback'],
                                                           'user_feedback': v['user_feedback'],
                                                          } for v in load_jsonl(generated_feedback_path)}

        self.input_fields = signature.input_fields
        self.input_fields['input'].json_schema_extra['format'] = str
        self.output_fields = signature.output_fields

        assert len(self.output_fields) == 1, "PoT only supports one output field."

        self.output_field_name = next(iter(self.output_fields))

        assert len(self.output_fields) == 1, "PoT only supports one output field."

        self.raw_code_generate = dspy.Predict(
        # self.raw_code_generate = Predict(
            dspy.Signature(
                self._generate_signature("raw_generate").fields,
                self._generate_instruction("raw_generate"),
            ),
        )
        self.code_generate = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("generate").fields,
                self._generate_instruction("generate"),
            ),
        )
        self.code_regenerate_from_compilation_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("refine_from_compilation_feedback").fields,
                self._generate_instruction("refine_from_compilation_feedback"),
            ),
        )
        self.code_regenerate_from_execution_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("refine_from_execution_feedback").fields,
                self._generate_instruction("refine_from_execution_feedback"),
            ),
        )
        self.code_regenerate_from_user_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("refine_from_user_feedback").fields,
                self._generate_instruction("refine_from_user_feedback"),
            ),
        )
        self.code_regenerate_from_execution_user_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("refine_from_execution_user_feedback").fields,
                self._generate_instruction("refine_from_execution_user_feedback"),
            ),
        )
        self.simulate_user_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("simulate_user_feedback").fields,
                self._generate_instruction("simulate_user_feedback"),
            ),
        )
        self.simulate_novice_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("simulate_novice_feedback").fields,
                self._generate_instruction("simulate_novice_feedback"),
            ),
        )
        self.execution_simulate_user_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("execution_simulate_user_feedback").fields,
                self._generate_instruction("execution_simulate_user_feedback"),
            ),
        )
        self.execution_simulate_novice_feedback = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("execution_simulate_novice_feedback").fields,
                self._generate_instruction("execution_simulate_novice_feedback"),
            ),
        )
        self.generate_answer = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("answer").fields,
                self._generate_instruction("answer"),
            ),
        )
        self.generate_answer = dspy.ChainOfThought(
            dspy.Signature(
                self._generate_signature("answer").fields,
                self._generate_instruction("answer"),
            ),
        )

    def _generate_signature(self, mode):
        signature_dict = dict(self.input_fields)

        fields_for_mode = {
            "raw_generate": {
                "generated_code": dspy.OutputField(format=str),
            },
            "generate": {
                "generated_code": dspy.OutputField(
                    prefix="Code:",
                    desc=f"{self.code_template} that satisfies user requirements",
                    format=str,
                ),
            },
            "refine_from_compilation_feedback": {
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "compilation_feedback": dspy.InputField(
                    prefix="Compilation Feedback:",
                    desc=f"error message from previously-generated {self.code_template}",
                    format=str,
                ),
                "generated_code": dspy.OutputField(
                    prefix="Code:",
                    desc=f"{self.code_template} that satisfies user requirements",
                    format=str,
                ),
            },
            "refine_from_execution_feedback": {
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "execution_feedback": dspy.InputField(
                    prefix="Execution Feedback:",
                    desc=f"error message from previously-generated {self.code_template}",
                    format=str,
                ),
                "generated_code": dspy.OutputField(
                    prefix="Code:",
                    desc=f"{self.code_template} that satisfies user requirements",
                    format=str,
                ),
            },
            "refine_from_user_feedback": {
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "user_feedback": dspy.InputField(
                    prefix="User Feedback:",
                    desc=f"(Simulated) User feedback from previously-generated {self.code_template}",
                    format=str,
                ),
                "generated_code": dspy.OutputField(
                    prefix="Code:",
                    desc=f"{self.code_template} that satisfies user requirements",
                    format=str,
                ),
            },
            "refine_from_execution_user_feedback": {
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "execution_feedback": dspy.InputField(
                    prefix="Execution Feedback:",
                    desc=f"error message from previously-generated {self.code_template}",
                    format=str,
                ),
                "user_feedback": dspy.InputField(
                    prefix="User Feedback:",
                    desc=f"(Simulated) User feedback from previously-generated {self.code_template}",
                    format=str,
                ),
                "generated_code": dspy.OutputField(
                    prefix="Code:",
                    desc=f"{self.code_template} that satisfies user requirements",
                    format=str,
                ),
            },
            "simulate_user_feedback": {
                "ground_truth_code": dspy.InputField(
                    prefix="Ground Truth Code:",
                    desc=f"Ground truth {self.code_template} to simulate user intention",
                    format=str,
                ),
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "user_feedback": dspy.OutputField(
                    prefix="User Feedback:",
                    desc=f"(Simulated) User feedback from previously-generated {self.code_template}\n---\n\n{EXPERT_FEEDBACK_EXAMPLE}",
                    format=str,
                ),
            },
            "simulate_novice_feedback": {
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "compilation_feedback": dspy.InputField(
                    prefix="Compilation Feedback:",
                    desc=f"error message from previously-generated {self.code_template}",
                    format=str,
                ),
                "user_feedback": dspy.OutputField(
                    prefix="User Feedback:",
                    desc=f"(Simulated) User feedback from previously-generated {self.code_template}\n---\n\n{NOVICE_FEEDBACK_EXAMPLE}",
                    format=str,
                ),
            },
            "execution_simulate_user_feedback": {
                "ground_truth_code": dspy.InputField(
                    prefix="Ground Truth Code:",
                    desc=f"Ground truth {self.code_template} to simulate user intention",
                    format=str,
                ),
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "execution_feedback": dspy.InputField(
                    prefix="Execution Feedback:",
                    desc=f"error message from previously-generated {self.code_template}",
                    format=str,
                ),
                "user_feedback": dspy.OutputField(
                    prefix="User Feedback:",
                    desc=f"(Simulated) User feedback from previously-generated {self.code_template}\n---\n\n{EXECUTION_EXPERT_FEEDBACK_EXAMPLE}",
                    format=str,
                ),
            },
            "execution_simulate_novice_feedback": {
                "previous_code": dspy.InputField(
                    prefix="Previous Code:",
                    desc=f"previously-generated {self.code_template} that errored",
                    format=str,
                ),
                "compilation_feedback": dspy.InputField(
                    prefix="Compilation Feedback:",
                    desc=f"error message from previously-generated {self.code_template}",
                    format=str,
                ),
                "execution_feedback": dspy.InputField(
                    prefix="Execution Feedback:",
                    desc=f"error message from previously-generated {self.code_template}",
                    format=str,
                ),
                "user_feedback": dspy.OutputField(
                    prefix="User Feedback:",
                    desc=f"(Simulated) User feedback from previously-generated {self.code_template}\n---\n\n{EXECUTION_NOVICE_FEEDBACK_EXAMPLE}",
                    format=str,
                ),
            },
            "answer": {
                "final_generated_code": dspy.InputField(
                    prefix="Code:",
                    desc=f"{self.code_template} that satisfies user requirements",
                    format=str,
                ),
                "compilation_feedback": dspy.InputField(
                    prefix="Compilation Feedback:",
                    desc=f"Compile result of previously-generated {self.code_template}",
                    format=str,
                ),
                self.output_field_name: self.signature.fields[self.output_field_name],
            },
        }
        signature_dict.update(fields_for_mode[mode])
        return dspy.Signature(signature_dict)

    def _generate_instruction(self, mode):
        mode_inputs = ", ".join(
            [
                f"`{field_name}`"
                for field_name in self._generate_signature(mode).input_fields
            ],
        )
        mode_outputs = f"`{self.output_field_name}`"
        if mode == "raw_generate":
            instr = []
        elif mode == "generate":
            instr = [
                f"You will be given {mode_inputs} and you will respond with {mode_outputs}.",
                f"Generating executable {self.code_template} that satisfies user requirements specification.",
                # f"After you're done with the computation, make sure the last line in your code evaluates to the correct value for {mode_outputs}.",
            ]
        elif mode in ["refine_from_compilation_feedback",
                      "refine_from_user_feedback",
                      "refine_from_execution_user_feedback",
                      "regenerate"]:
            instr = [
                f"You are given {mode_inputs} due to an error in previous code.",
                "Your task is to correct the error and provide the new `generated_code`.",
            ]
        elif mode in ["simulate_user_feedback", "execution_simulate_user_feedback"]:
            instr = [
                f"You are given {mode_inputs} to simulate user feedback that compares the `previous_code` and the `ground_truth_code`.",
                "Your task is to provide the simulated `user_feedback` that highlights specific areas where the `previous_code` deviates from the `ground_truth_code` and suggests improvements or corrections.",
                "- You SHOULD NOT leak `ground_truth_code` in the simulated user feedback.",
                "- Do not generate updated code.",
                "- Do not reveal that you can access the `ground_truth_code`. Only indirect information is allowed.",
            ]
        elif mode in ["simulate_novice_feedback", "execution_simulate_novice_feedback"]:
            feedback_list = ", ".join(
            [
                f"`{field_name}`"
                for field_name in self._generate_signature(mode).input_fields
                if 'feedback' in field_name
            ],
        )
            instr = [
                f"You are given {mode_inputs} due to an error in previous code.",
                "Your task is to provide the simulated `user_feedback` that  to simulate user feedback that specifies the problem in the `previous_code`.",
                "- Do not generate updated code.",
                "- Note that the `previous_code` is generated by an LLM, not by the user that you are simulating.",
                f"- Ensure that the `user_feedback` only includes information derived from {feedback_list}, without any additional details.",

            ]
        else:  # mode == 'answer'
            instr = [
                f"Return the final code {mode_inputs} in markdown format.",
            ]

        return "\n".join(instr)


    def parse_code(self, code_data):
        if type(code_data) is str:
            return code_data, None
        code = (
            code_data.get("generated_code", "").split("\n\n---\n\n", 1)[0].split("\n\n\n", 1)[0]
        )
        # print(f'{code=}')
        code_match = None
        if self.language.lower() == "python":
            code_match = re.search(r"```python[ \n](.*?)[ \n]```?", code, re.DOTALL)
        if code_match is None:
            code_match = re.search(r"```[ \n](.*?)[ \n]```?", code, re.DOTALL)
        code_block = (code_match.group(1) if code_match else code).replace('```', '')#.replace("\\n", "\n")
        if not code_block:
            return code, "Error: Empty code after parsing."
        # lines = code_block.split("\n")
        # last_line_match = re.match(r"^(\w+)\s*=", lines[-1].strip())
        # if last_line_match and len(lines) > 1:
        #     code_block += "\n" + last_line_match.group(1)
        # else:
        #     code_block = re.sub(
        #         r"([a-zA-Z_]\w* *=.*?)(?=[a-zA-Z_]\w* *=)", r"\1\n", code_block,
        #     )
        #     code_block = re.sub(
        #         r"([a-zA-Z_]\w* *=.*?)([a-zA-Z_]\w*)$", r"\1\n\2", code_block,
        #     )
        return code_block, None


    def get_compilation_feedback(self, code_data):
        code, error = self.parse_code(code_data)
        # FIXME: Don't try to execute the code if it didn't parse
        error = compile_code(code)

        if error is None:
            compilation_feedback = NO_SYNTAX_ERRORS
        else:
            compilation_feedback = error

        return code, compilation_feedback

    def get_execution_feedback(self, code, task_id, trim=False, front_trim=2000, rear_trim=4000):
        execution_result = self.execution_results_dict[task_id]
        # assert code == execution_result['code'], f"[CODE]\n{code}\n\n[EXCUTED CODE]\n{execution_result['code']}"
        if execution_result['status'] == "pass":
            execution_feedback = PASSED_ALL_TEST_RUNS
        elif self.unit_test:
            unit_test_names = extract_methods_from_class(self.dataset[task_id].test)[:NUM_UNIT_TESTS]
            execution_feedback = "\n".join([f"{tc_id.upper()}\n{tc_result}\n"
                                                 for tc_id, tc_result in execution_result['execution_feedback'].items() if tc_id in unit_test_names])
            if execution_feedback == "":
                execution_feedback = PASSED_ALL_TEST_RUNS
                # print(f"{unit_test_names=}")
                # print(f"{execution_feedback=}")
                # full_execution_feedback = "\n".join([f"{tc_id.upper()}\n{tc_result}\n"
                #                                      for tc_id, tc_result in execution_result['execution_feedback'].items()])
                # print(f"{full_execution_feedback=}")
                # exit(1)
        else:
            execution_feedback = "\n".join([f"{tc_id.upper()}\n{tc_result}\n"
                                                 for tc_id, tc_result in execution_result['execution_feedback'].items()])


        if len(execution_feedback) >= 8000 or trim:
            if len(execution_feedback.splitlines()) >= 10:
                window = 5
            elif len(execution_feedback.splitlines()) == 1:
                window = 1
            else:
                window = len(execution_feedback.splitlines()) // 2
            front = "\n".join(execution_feedback.splitlines()[:window])[:front_trim]
            rear = "\n".join(execution_feedback.splitlines()[-window:])[-rear_trim:]
            execution_feedback = front+'\n...\n'+rear
            # if self.tokenizer is not None and len(self.tokenizer.tokenize(execution_feedback)) > 1500:
            #     tokenized_front = self.tokenizer.tokenize(front)
            #     tokenized_rear = self.tokenizer.tokenize(rear)
            #     if len(tokenized_front) > len(tokenized_rear):
            #         tokenized_front = tokenized_front[:1500 - len(tokenized_rear) - 10]
            #     elif len(tokenized_front) <= len(tokenized_rear):
            #         tokenized_rear = tokenized_rear[-1500 + len(tokenized_front) + 10:]
            #     execution_feedback = self.tokenizer.convert_tokens_to_string(tokenized_front) + '\n...\n' + self.tokenizer.convert_tokens_to_string(tokenized_rear)

            print("EXECUTION FEEDBACK:")
            print(execution_feedback)
            # print(len(execution_feedback))

        return execution_feedback
    def was_prev_code_passed(self, task_id):
        execution_result = self.execution_results_dict[task_id]
        return execution_result['status'] == "pass"

    def get_simulated_user_feedback(self, _input_kwargs, code, task_id):
        if self.generated_feedback_dict is not None:
            user_feedback = self.generated_feedback_dict[task_id]['user_feedback']
            return user_feedback

        gt_code = self.dataset[task_id].code_prompt+self.dataset[task_id].canonical_solution
        if self.cheating:
            user_feedback = f"Ground truth code is:\n```\n{gt_code}\n```"
        else:
            input_kwargs = copy.deepcopy(_input_kwargs)
            with dspy.context(lm=self.user_feedback_simulator):
                input_kwargs.update({"previous_code": f"```\n{code}\n```"})
                if self.user_expertise == 'expert':
                    input_kwargs.update({"ground_truth_code": f"```\n{gt_code}\n```", })
                    if input_kwargs['execution_feedback'] not in [None, PASSED_ALL_TEST_RUNS]:
                        _user_feedback = self.execution_simulate_user_feedback(**input_kwargs)
                    else:
                        _user_feedback = self.simulate_user_feedback(**input_kwargs)
                elif self.user_expertise == 'novice':
                    if self.execution_feedback:
                        if input_kwargs['execution_feedback'] not in [None, PASSED_ALL_TEST_RUNS]:
                            _user_feedback = self.execution_simulate_novice_feedback(**input_kwargs)
                        else:
                            if input_kwargs['execution_feedback'] == PASSED_ALL_TEST_RUNS:
                                return None
                            _user_feedback = self.simulate_novice_feedback(**input_kwargs)
                    else:
                        if input_kwargs['compilation_feedback'] not in [None, NO_SYNTAX_ERRORS]:
                            _user_feedback = self.simulate_novice_feedback(**input_kwargs)
                        else:
                            return None
                else:
                    raise ValueError(f"Unrecognized user_expertise: {self.user_expertise}")
            user_feedback = (
                _user_feedback.get("user_feedback", "").split("---", 1)[0].split("\n\n\n", 1)[0]
            )
            if self.user_expertise == 'expert':
                user_feedback = user_feedback.split("\n```")[0]

        return user_feedback




    def forward(self, **kwargs):
        input_kwargs = {
            field_name: kwargs[field_name] for field_name in self.input_fields
        }
        task_id = kwargs["task_id"]
        if self.use_generated_code or self.iteration > 1:
            code_data = self.generated_code_dict[task_id]
        elif self.raw_generate:
            # input_kwargs["new_signature"] = "->"
            code_data = self.raw_code_generate(**input_kwargs)
        else:
            code_data = self.code_generate(**input_kwargs)
        code, error = self.parse_code(code_data)
        if error is not None:
            print(error)

        compilation_feedback = None
        execution_feedback = None
        simulated_user_feedback = None
        hop = self.iteration
        if self.iteration > 1 or self.use_generated_code:
            if self.was_prev_code_passed(task_id):
                print("Already solved")
                return {"final_generated_code": code,
                        "compilation_feedback": compilation_feedback,
                        "execution_feedback": execution_feedback,
                        "user_feedback": simulated_user_feedback,
                        "iteration": hop}
        try:
            while hop < self.iteration+self.max_iters:
                if self.compilation_feedback:
                    code, compilation_feedback = self.get_compilation_feedback(code_data)

                if compilation_feedback not in [None, NO_SYNTAX_ERRORS]:
                    print("Error in code compilation")
                    input_kwargs.update({"previous_code": code, "compilation_feedback": compilation_feedback})
                    if self.simulated_user_feedback and self.user_expertise == 'novice':
                        pass
                    else:
                        none_flag = True
                        while none_flag:
                            try:
                                code_data = self.code_regenerate_from_compilation_feedback(**input_kwargs)
                            except AttributeError as e:
                                print(e)
                                compilation_feedback += " "
                                input_kwargs.update({"compilation_feedback": compilation_feedback})
                                continue
                            none_flag = False

                        hop += 1
                        continue

                input_kwargs.update({"final_generated_code": code, "compilation_feedback": compilation_feedback})

                if self.execution_feedback:
                    execution_feedback = self.get_execution_feedback(code, task_id)

                if execution_feedback not in [None, PASSED_ALL_TEST_RUNS]:
                    if self.simulated_user_feedback:
                        pass
                    else:
                        print("Error in code execution")
                        input_kwargs.update({"previous_code": code, "execution_feedback": execution_feedback})
                        none_flag = True
                        while none_flag:
                            try:
                                code_data = self.code_regenerate_from_execution_feedback(**input_kwargs)
                            except AttributeError as e:
                                print(e)
                                execution_feedback += " "
                                input_kwargs.update({"execution_feedback": execution_feedback})
                                continue
                            none_flag = False

                        hop += 1
                        break

                if self.execution_feedback or self.generated_feedback_dict is None:
                    input_kwargs.update({"execution_feedback": execution_feedback})

                if self.simulated_user_feedback:
                    simulated_user_feedback = self.get_simulated_user_feedback(input_kwargs, code, task_id)
                    input_kwargs.update({"previous_code": code, "user_feedback": simulated_user_feedback})

                    none_flag = True
                    exit_flag = False
                    trim = False
                    front_trim = 2000
                    rear_trim = 4000
                    while none_flag:
                        try:
                            if execution_feedback not in [None, PASSED_ALL_TEST_RUNS]:
                                try:
                                    code_data = self.code_regenerate_from_execution_user_feedback(**input_kwargs)
                                except Exception as e:
                                    print(e)
                                    if not trim:
                                        trim = True
                                    elif front_trim > rear_trim:
                                        front_trim -= 1000
                                    elif front_trim <= rear_trim:
                                        rear_trim -= 1000
                                    assert front_trim >= 0 and rear_trim >= 0, "Input is too long even after we remove execution feedback"
                                    execution_feedback = self.get_execution_feedback(code, task_id, trim=trim, front_trim=front_trim, rear_trim=rear_trim)
                                    input_kwargs.update({"execution_feedback": execution_feedback})
                                    continue
                            elif self.user_expertise == 'expert':
                                # print(input_kwargs)
                                try:
                                    code_data = self.code_regenerate_from_user_feedback(**input_kwargs)
                                except AssertionError as e:
                                    code_data = code
                            elif self.user_expertise == 'novice':
                                if compilation_feedback not in [None, NO_SYNTAX_ERRORS]:
                                    try:
                                        code_data = self.code_regenerate_from_user_feedback(**input_kwargs)
                                    except AssertionError as e:
                                        code_data = code
                                else:
                                    exit_flag = True
                        except AttributeError as e:
                            print(e)
                            simulated_user_feedback += " "
                            input_kwargs.update({"user_feedback": simulated_user_feedback})
                            continue
                        none_flag = False

                    if exit_flag:
                        break
                    hop += 1
                    # continue
                    break

                hop += 1
                break
        except Exception as e:
            print(e)
            traceback.print_exc()
            exit()


        code, error = self.parse_code(code_data)
        # answer_gen_result = self.generate_answer(**input_kwargs)
        return {"final_generated_code": code,
                "compilation_feedback": compilation_feedback,
                "execution_feedback": execution_feedback,
                "user_feedback": simulated_user_feedback,
                "iteration": hop}
