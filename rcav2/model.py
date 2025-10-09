# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import dspy  # type: ignore[import-untyped]
import llm
import os


def init_dspy() -> None:
    dspy.settings.configure(track_usage=True)
    dspy.configure(
        lm=dspy.LM(
            "gemini/gemini-2.5-flash",
            temperature=0.5,
            max_tokens=16384,
            api_key=os.environ["LLM_GEMINI_KEY"],
        )
    )


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
                events="usage",
            )


async def query(env, model, system, prompt):
    env.log.info("Analyzing build with %s using %s bytes", model, len(prompt))
    model = llm.get_async_model(model)
    response = model.prompt(prompt, system=system)
    async for chunk in response:
        yield (chunk, "chunk")
    usage = await response.usage()
    if usage:
        yield (dict(input=usage.input, output=usage.output), "usage")
