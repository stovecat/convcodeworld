import dspy

AZURE_OPENAI_MODEL_LIST = ["gpt-4o", "gpt-4-turbo-2024-04-09", "gpt-4-0613", "gpt-4o-mini", "gpt-35-turbo-0613", "gpt-35-turbo-instruct-0914"]

def load_api(path: str):
    api_keys = []
    with open(path, 'r') as f:
        for line in f:
            key = line.strip()
            api_keys.append(key)
    return api_keys

def get_azure_name(model_name):
    if model_name in ["gpt-4o", "gpt-4o-2024-05-13"]:
        # Model version: 2024-05-13
        return "sfc-cortex-analyst-dev"
    elif model_name == "gpt-4o-2024-08-06":
        return "rajhans-testing-deployment"
    elif model_name == "gpt-4-turbo-2024-04-09":
        # Model version: turbo-2024-04-09
        return "sfc-ml-gpt4-turbo"
    elif model_name == "gpt-4-0613":
        # Model version: 0613
        # return "sfc-ml-sweden-gpt4-managed"
        return "sc-merida-dev-copilot"
    elif model_name == "gpt-4o-mini":
        # Model version: 2024-07-18
        return "cortex-analyst-gpt-4o-mini-dev"
    elif model_name == "gpt-35-turbo-0613":
        return "sfc-ml-sweden-gpt35-chat-deployment"
    elif model_name == "gpt-35-turbo-instruct-0914":
        return "sfc-ml-sweden-gpt35-deployment"
    elif model_name == "gpt-4-32k":
        return "sfc-ml-snowpilot-gpt-4-32k"
    else:
        raise NotImplementedError(f"Model {model_name} not implemented")

def get_azure_lm(_model_name):
    model_name = get_azure_name(_model_name)
    keys = load_api(".api_key")
    api_version = '2023-03-15-preview'
    url = f"https://sfc-ml-sweden.openai.azure.com/openai/deployments/{model_name}/chat/completions?api-version={api_version}"

    # Set up the LM.
    lm = dspy.AzureOpenAI(api_base=url, api_key=keys[0],
                          api_version=api_version, model=model_name, max_tokens=2048, stop=["\n\n---\n\n"])

    return lm

def get_openai_lm(model_name):
    keys = load_api(".api_key")
    lm = dspy.OpenAI(model=model_name, api_key=keys[0], max_tokens=2048, stop=["\n\n---\n\n"])

    return lm
