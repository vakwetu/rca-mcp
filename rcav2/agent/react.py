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
from rcav2.report import Report


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

    report: Report = dspy.OutputField()


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
    job: rcav2.agent.zuul.Job | None,
    errors: rcav2.errors.Report,
    worker: Worker,
    trace_storage=None,
) -> str:
    if not job:
        job = rcav2.agent.zuul.Job(description="", actions=[])
    await worker.emit("Calling RCAAccelerator", "progress")
    errors_count = dict()
    for logfile in errors.logfiles:
        errors_count[logfile.source] = len(logfile.errors)
    agent.set_lm(rcav2.model.get_lm("gemini-2.5-pro", max_tokens=1024 * 1024))
    result = await agent.acall(job=job, errors=errors_count)
    await rcav2.model.emit_dspy_usage(result, worker)

    # Store LLM interactions in Opik if trace storage is available
    if trace_storage and trace_storage.is_available():
        try:
            history = rcav2.model.get_dspy_history()
            interactions = rcav2.model.extract_llm_interactions(history)

            for interaction in interactions:
                await trace_storage.store_llm_interaction(
                    prompt=interaction['prompt'],
                    response=interaction['response'],
                    model=interaction['model'],
                    usage=interaction['usage'],
                    worker=worker
                )
        except Exception as e:
            await worker.emit(f"Failed to store LLM interactions: {e}", event="error")

    return result.report
