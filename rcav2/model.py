# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import llm


def query(env, output, model, system, prompt):
    env.log.info("Analyzing build with %s using %s bytes", model, len(prompt))
    model = llm.get_model(model)
    response = model.prompt(prompt, system=system)
    for chunk in response:
        print(chunk, end="", file=output)
    print(file=output)
    usage = response.usage()
    if usage:
        env.log.info("Request usage: %s -> %s", usage.input, usage.output)


async def stream(env, model, system, prompt):
    env.log.info("Analyzing build with %s using %s bytes", model, len(prompt))
    model = llm.get_async_model(model)
    response = model.prompt(prompt, system=system)
    async for chunk in response:
        yield (chunk, "chunk")
    usage = await response.usage()
    if usage:
        yield (f"{usage.input} -> {usage.output}", "usage")
