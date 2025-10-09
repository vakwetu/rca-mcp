# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import dspy  # type: ignore[import-untyped]
import llm
import os


def init_dspy():
    dspy.configure(
        lm=dspy.LM(
            "gemini/gemini-2.5-flash",
            temperature=0.5,
            max_tokens=16384,
            api_key=os.environ["LLM_GEMINI_KEY"],
        )
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
