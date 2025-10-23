# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import dspy  # type: ignore[import-untyped]

import rcav2.errors
import rcav2.prompt
import rcav2.agent.zuul
from rcav2.report import Report
from rcav2.worker import Worker


class RCAAccelerator(dspy.Signature):
    """You are a CI engineer, your goal is to find the RCA of this build failure.

    You are given a description of the job and the errors found in the logs.

    Your investigation strategy should be as follows:
    1.  **Recognize Symptoms:** The errors in `job-output.txt` are often just symptoms. The actual root cause likely occurred earlier.
    2.  **Trace Back to the Root Cause:** Use the log file list to examine logs that came before `job-output.txt`. These earlier logs are critical for finding the initial point of failure.
    3.  **Analyze All Evidence:** It is crucial that you analyze all the provided errors before drawing a conclusion. Do not stop at the first error you find.
    4.  **Identify the Root Cause:** After a full analysis, identify the definitive root cause.
    """

    job: rcav2.agent.zuul.Job = dspy.InputField()

    # TODO: provide tools instead to access the raw reports. Then remove the errors input
    errors: str = dspy.InputField()

    report: Report = dspy.OutputField()


def make_agent() -> dspy.Predict:
    return dspy.Predict(RCAAccelerator, max_tokens=1024 * 1024)


async def call_agent(
    agent: dspy.Predict,
    job: rcav2.agent.zuul.Job | None,
    errors: rcav2.errors.Report,
    worker: Worker,
    trace_storage=None,
) -> Report:
    if not job:
        job = rcav2.agent.zuul.Job(description="", actions=[])
    await worker.emit("Calling RCAAccelerator", "progress")
    agent.set_lm(rcav2.model.get_lm("gemini-2.5-pro", max_tokens=1024 * 1024))
    errors_report = rcav2.prompt.report_to_prompt(errors)
    result = await agent.acall(job=job, errors=errors_report)
    await rcav2.model.emit_dspy_usage(result, worker)

    # Store LLM interactions in Opik if trace storage is available
    if trace_storage and trace_storage.is_available():
        try:
            history = rcav2.model.get_dspy_history()
            interactions = rcav2.model.extract_llm_interactions(history)

            for interaction in interactions:
                await trace_storage.store_llm_interaction(
                    prompt=interaction["prompt"],
                    response=interaction["response"],
                    model=interaction["model"],
                    usage=interaction["usage"],
                    worker=worker,
                )
        except Exception as e:
            await worker.emit(f"Failed to store LLM interactions: {e}", event="error")

    return result.report
