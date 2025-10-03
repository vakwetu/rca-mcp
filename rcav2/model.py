# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import rcav2.dspy_agent as dspy_agent


async def query(env, model, system, prompt):
    env.log.info("Analyzing build with DSPy using %s bytes", len(prompt))
    # Delegate to DSPy agent for analysis, preserving (message, event) protocol
    async for item in dspy_agent.analyze_report(prompt):
        yield item
