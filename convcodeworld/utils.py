import json
import dill as pickle

def load_json(path):
    with open(path, "r") as fp:
        data = json.load(fp)
    return data

def dump_json(data, path):
    with open(path, "w") as fp:
        json.dump(data, fp)

def load_jsonl(path):
    data = []
    with open(path, "r") as fp:
        for line in fp.readlines():
            data.append(json.loads(line))
    return data

def dump_jsonl(data, path):
    with open(path, 'w') as fp:
        for d in data:
            json.dump(d, fp)
            fp.write('\n')


def dump_pkl(data, path):
    with open(path, "wb") as fp:
        pickle.dump(data, fp, pickle.HIGHEST_PROTOCOL)


def load_pkl(path):
    with open(path, "rb") as fp:
        data = pickle.load(fp)
    return data