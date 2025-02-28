from pydantic import BaseModel, Field
from dspy.datasets.dataset import Dataset
from datasets import load_dataset
from huggingface_hub.hf_api import DatasetInfo

# Monkey patch the DatasetInfo class to handle missing tags
def new_init(self, *args, **kwargs):
    kwargs.setdefault('tags', [])  # Add default empty tags if missing
    original_init(self, *args, **kwargs)

# Store the original __init__ and replace it
original_init = DatasetInfo.__init__
DatasetInfo.__init__ = new_init

class BigCodeBench(Dataset):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        dataset = load_dataset("bigcode/bigcodebench")
        self._test = dataset['v0.1.0_hf']

class InitInput(BaseModel):
    context: str = Field(description="Related code")
    query: str = Field(description="The initial problem description from user")

class Output(BaseModel):
    code: str = Field(description="The code prediction")

