# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import dspy  # type: ignore[import-untyped]
import os


def get_lm(name: str, max_tokens: int) -> dspy.LM:
    return dspy.LM(
        f"gemini/{name}",
        temperature=0.5,
        max_tokens=max_tokens,
        api_key=os.environ["LLM_GEMINI_KEY"],
    )


def init_dspy() -> None:
    dspy.settings.configure(track_usage=True)
    dspy.configure(lm=get_lm("gemini-2.5-flash", 16384))


async def emit_dspy_usage(result, worker):
    usages = result.get_lm_usage()
    if usages:
        for model, usage in usages.items():
            await worker.emit(
                dict(
                    model=model,
                    input=usage.get("prompt_tokens"),
                    output=usage.get("completion_tokens"),
                ),
                event="usage",
            )
