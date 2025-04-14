from transformers import pipeline

messages = [
    {"role": "user", "content": "Who are you?"},
]

pipe = pipeline("text-generation", model="jinaai/ReaderLM-v2")
pipe(messages)