import pandas as pd
import datasets
import json
import os

"""
results = pipeline(
    task = str,
    dataset_path = str,
    train_split = str,
    test_split = str,
    columns_name = list,
    preprocessing = fn,
    fewshots = int:0,
    prompt = str, # jinja
    max_samples = int:-1, # by default, the length of the test split
    threads = int:1, # by default 1
    threads_timeout = int:100, # by default 100
    records_path = str, # by default ./records
    resume_from_records = bool, # True
    temperature = int:0, # by default 0
)
"""

# sys_msg = "Respond only positive or negative sentiment: "
def create_chat_prompt(sys_msg, input_text):
    return [
        {"role": "system", "content": sys_msg}, 
        {"role": "user", "content": input_text}
    ]

def create_chat_example(content, label):
    return [
        {"role": "system", "content": content, "name": "example_user"},
        {"role": "system", "content": label, "name": "example_assistant"},
    ]


def pipeline(
    input_column_name,
    target_column_name,
    prompt,
    api_key,
    data_dir='.',
    dataset_name="arbml/easc",
    preprocessing_fn=None,
    train_split="train",
    test_split=None,
    records_path="easc.jsonl",
    threads = 1,
    threads_timeout=100,
):
    
    train_dataset = datasets.load_dataset(dataset_name, split=train_split)
    if test_split is not None:
        test_dataset = datasets.load_dataset(dataset_name, split=test_split)

    if resume_from_records:
        success_ids = get_success_record_ids(records_path=records_path)
        unsuccess_ids = set(range(len(test_dataset))) - set(success_ids)
        test_dataset = test_dataset.select(unsuccess_ids)
    print(test_dataset)

    # preprocess the dataset
    if preprocessing_fn is not None:
        train_dataset = train_dataset.map(preprocessing_fn)
        test_dataset = test_dataset.map(preprocessing_fn)

    dev_df = train_dataset.to_pandas()
    dev_df["sample"] = dev_df.apply(lambda x: create_chat_example(x[input_column_name], x[target_column_name]), axis=1)
    dev_df[["sample"]].to_json(f'{data_dir}/few_shot.jsonl', lines=True, orient="records",force_ascii=False)

    test_df = test_split
    test_df["input"] = test_df[input_column_name].apply(lambda x: create_chat_prompt(prompt, x))
    test_df["ideal"] = test_df[target_column_name]
    test_df[["input", "ideal"]].to_json(f'{data_dir}/samples.jsonl', lines=True, orient="records",force_ascii=False)

    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["EVALS_THREADS"]=f"{threads}"
    os.environ["EVALS_THREAD_TIMEOUT"]=f"{threads_timeout}"

    resume_from_records = True


def get_success_record_ids(records_path):
    with open(records_path, "r") as records_file:
        records_str = records_file.read().splitlines()
        records = [json.loads(record_str) for record_str in records_str]
    records = list(filter(lambda record: "type" in record.keys(), records))
    success_type = "summarization"
    success_records = list(
        filter(
            lambda record: record["type"] == success_type,
            records,
        )
    )
    success_records = sorted(
        success_records,
        key=lambda record: int(record["sample_id"].split(".")[-1]),
    )
    success_ids = [
        int(record["sample_id"].split(".")[-1]) for record in success_records
    ]
    return sorted(set(success_ids))
