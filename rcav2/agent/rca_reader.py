# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

"""
A next-gen rca agent that reads the errors as needed
"""

import dspy  # type: ignore[import-untyped]

import rcav2.errors
import rcav2.prompt
import rcav2.model
import rcav2.agent.zuul
from rcav2.worker import Worker


class RCAAccelerator(dspy.Signature):
    """You are a CI engineer, your goal is to find the RCA of this build failure.

    You are given a description of the job and the list of logs file.
    Use the read_errors tool to identify the root cause.
    Starts with the job-output.txt, and check the other logs to collect evidence.
    Don't stop reading errors until the root cause is fully diagnosed.
    """

    job: rcav2.agent.zuul.Job = dspy.InputField()

    errors: dict[str, int] = dspy.InputField(
        desc="list of source and their error count"
    )

    # TODO: use structured output
    report: str = dspy.OutputField()


def make_agent(errors: rcav2.errors.Report, worker: Worker) -> dspy.Predict:
    async def read_errors(source: str) -> list[rcav2.errors.Error]:
        """Read the errors contained in a source log, including the before after context"""
        await worker.emit(f"Checking {source}", "progress")
        for logfile in errors.logfiles:
            if logfile.source == source:
                return logfile.errors
        return []

    return dspy.ReAct(RCAAccelerator, tools=[read_errors])


async def call_agent(
    agent: dspy.Predict,
    job: rcav2.agent.zuul.Job,
    errors: rcav2.errors.Report,
    worker: Worker,
) -> str:
    await worker.emit("Calling RCAAccelerator", "progress")
    errors_count = dict()
    for logfile in errors.logfiles:
        errors_count[logfile.source] = len(logfile.errors)
    agent.set_lm(rcav2.model.get_lm("gemini-2.5-flash", max_tokens=1024 * 1024))
    result = await agent.acall(job=job, errors=errors_count)
    await rcav2.model.emit_dspy_usage(result, worker)
    return result.report
