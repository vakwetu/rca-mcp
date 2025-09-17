# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import llm


async def query(env, model, system, prompt):
    env.log.info("Analyzing build with %s using %s bytes", model, len(prompt))
    model = llm.get_async_model(model)
    response = model.prompt(prompt, system=system)
    async for chunk in response:
        yield (chunk, "chunk")
    usage = await response.usage()
    if usage:
        yield (dict(input=usage.input, output=usage.output), "usage")
