from openai import OpenAI
import os

SYSTEM_PROMPT = "..."

class LLMService:
    def __init__(self) -> None:
        self.client = OpenAI()

    def ask(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        result = completion.choices[0].message.content

        if not result:
            raise ValueError("No result from LLM")
        else:
            return result