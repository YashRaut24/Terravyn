import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Sequence

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=api_key)


def generate_response(
    system_prompt: str,
    messages: Sequence[ChatCompletionMessageParam],
    output_format: Literal["text", "json"] = "text",
) -> str | dict[str, object]:
    completion = _get_client().chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            *messages,
        ],
        response_format={
            "type": "json_object" if output_format == "json" else "text"
        },
    )
    content = completion.choices[0].message.content
    if content is None:
        raise RuntimeError("The LLM returned no text content")

    if output_format == "json":
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("The LLM response must be a JSON object")
        return result

    return content
