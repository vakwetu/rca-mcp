# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

"""
A next-gen rca agent that reads the errors as needed
"""

import dspy  # type: ignore[import-untyped]

import rcav2.models.errors
import rcav2.model
import rcav2.agent.ansible
from rcav2.worker import Worker
from rcav2.models.report import Report


class RCAAccelerator(dspy.Signature):
    """
    You are a CI engineer, your goal is to find the RCA of this build failure.

    ============================================================================
    INVESTIGATION STRATEGY
    ============================================================================

    1. **Start with `job-output.txt`:**
       - Use the `read_errors` tool on this file first
       - This identifies the final error or symptom of the failure

    2. **Trace back to the root cause:**
       - The errors in `job-output.txt` are often just symptoms
       - The actual root cause likely occurred earlier
       - The earlier logs are critical for finding the initial point of failure

    3. **Follow the error trail:**
       - Within each file you inspect, follow the sequence of errors
       - Understand the full context of how the problem developed
       - The ultimate root cause is somewhere in the available logs
       - Use the `search_errors` tool to find all the evidences
       - Don't stop reading errors until the root cause is fully diagnosed

    4. **Synthesize your findings:**
       - Connect the events from the early logs with the final failure shown in `job-output.txt`
       - Build a complete and accurate root cause analysis

    5. **Identify all possible root causes:**
       - After a full analysis, identify all possible root causes (usually 1-3 possibilities)

    ============================================================================
    ROOT CAUSE REPORTING
    ============================================================================

    Provide a Summary:
    - Provide a concise summary of the root cause analysis
    - The summary should be a brief overview that helps someone quickly understand what went wrong
    - The summary should include the stage at which the root cause occurred
    - The summary should also include a small table showing the timeline
      for the errors that you have identified

    You should identify all possible root causes of the failure.

    For each root cause, provide:
    - cause: The root cause of the failure
    - evidences: The evidence that supports the root cause

    You should order the root causes by the likelihood of the root cause being the actual
    root cause, starting with the most likely root cause.
    """

    job: rcav2.agent.ansible.Job = dspy.InputField()

    errors: dict[str, int] = dspy.InputField(
        desc="list of source and their error count"
    )

    log_url: str | None = dspy.InputField(
        desc="URL to the build logs for stage analysis"
    )

    report: Report = dspy.OutputField()


def make_agent(errors: rcav2.models.errors.Report, worker: Worker, env) -> dspy.ReAct:
    async def read_errors(source: str) -> list[rcav2.models.errors.Error]:
        """Read the errors contained in a source log, including the before after context"""
        await worker.emit(f"Checking {source}", "progress")
        for logfile in errors.logfiles:
            if logfile.source == source:
                return logfile.errors
        return []

    async def search_jira_issues(
        query: str, max_results: int | None = 50
    ) -> list[dict[str, str | None]]:
        """Searches jira issues using JQL (Jira query language).
        Returns list of issues with key, url, summary, status, and description.
        The 'url' field contains the full link to the JIRA ticket.
        Returns 50 results by default, for more results set max_results.
        Use the 'key' field from results with get_jira_issue for more details.
        If JIRA_RCA_PROJECT is configured, automatically filters to that project.

        JQL Query Syntax - IMPORTANT:
        - Text search: text ~ "error message" (quotes required for phrases)
        - Summary search: summary ~ "keyword"
        - Description search: description ~ "error text"
        - Multiple terms: summary ~ "cert-manager" AND text ~ "timeout"
        - OR condition: summary ~ "error" OR description ~ "failure"

        Valid operators: ~ (contains), !~, =, !=, IN, NOT IN
        Always use ~ for text searches with quoted strings."""
        if not env.jira:
            await worker.emit(
                "JIRA client not available. Set JIRA_URL, JIRA_API_KEY and JIRA_RCA_PROJECTS", "error"
            )
            return []

        await worker.emit(
            f"Searching issues with query: {query}, max_results: {max_results}",
            "progress",
        )
        return env.jira.search_jira_issues(query, max_results)

    async def search_slack_messages(
        query: str, count: int | None = 20
    ) -> list[dict[str, str | None]]:
        """Searches slack messages.
        Returns list of messages with text, user, permalink, and channel.
        Returns 20 results by default, for more results set count.
        """
        if not env.slack:
            await worker.emit(
                "Slack client not available. Set SLACK_API_KEY and SLACK_SEARCH_CHANNELS",
                "error",
            )
            return []

        await worker.emit(
            f"Searching slack with query: {query}, count: {count}",
            "progress",
        )
        return env.slack.search_messages(query, count)

    async def check_build_log_directory(directory_path: str) -> dict[str, str | bool]:
        """Check if a directory exists in the build logs.

        Args:
            directory_path: The directory path to check for (e.g., '/tmp/build', '/workspace')

        Returns:
            Dictionary with 'exists' (bool) and 'message' (str) fields
        """
        if not errors.log_url:
            return {"exists": False, "message": "No log URL provided"}

        try:
            await worker.emit(
                f"Checking for directory '{directory_path}' in build logs", "progress"
            )

            # Construct the URL to check: log_url/directory_path
            # Remove leading slash from directory_path to avoid double slashes
            clean_path = directory_path.lstrip("/")
            check_url = f"{errors.log_url.rstrip('/')}/{clean_path}"

            # Try to access the directory URL
            response = await env.httpx.get(check_url, timeout=30.0)

            if response.status_code == 200:
                return {
                    "exists": True,
                    "message": f"Directory '{directory_path}' exists in build logs (accessible at {check_url})",
                }
            elif response.status_code == 404:
                return {
                    "exists": False,
                    "message": f"Directory '{directory_path}' not found in build logs (404 at {check_url})",
                }
            else:
                return {
                    "exists": False,
                    "message": f"Directory '{directory_path}' check failed with status {response.status_code} at {check_url}",
                }

        except Exception as e:
            return {"exists": False, "message": f"Error checking directory: {str(e)}"}

    return dspy.ReAct(
        RCAAccelerator,
        tools=[
            read_errors,
            search_jira_issues,
            search_slack_messages,
            check_build_log_directory,
        ],
    )


async def call_agent(
    agent: dspy.ReAct,
    job: rcav2.agent.ansible.Job | None,
    errors: rcav2.models.errors.Report,
    worker: Worker,
) -> Report:
    if not job:
        job = rcav2.agent.ansible.Job(description="", actions=[])

    # Add log URL to job description if available
    if log_url := errors.log_url:
        job.description += f"\n\nBuild Log URL: {log_url}"

    await worker.emit("Calling RCAAccelerator", "progress")
    errors_count = dict()
    for logfile in errors.logfiles:
        errors_count[logfile.source] = len(logfile.errors)
    agent.set_lm(rcav2.model.get_lm("gemini-2.5-pro", max_tokens=1024 * 1024))
    result = await agent.acall(job=job, errors=errors_count, log_url=log_url)
    await rcav2.model.emit_dspy_usage(result, worker)
    return result.report
