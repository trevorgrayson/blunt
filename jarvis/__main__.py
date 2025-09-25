import sys
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    input=sys.stdin.read()
)

print(response.output_text)

