# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import dspy  # type: ignore[import-untyped]
from pydantic import BaseModel

import rcav2.git
from rcav2.worker import Worker


class Job(BaseModel):
    description: str
    actions: list[str]


class DSPyAnsibleOracle(dspy.Signature):
    """You are a Ansible Playbooks knowledge service agent that helps user understand the purpose of a Zuul job.

    You are given a playbook path, and you should use tool in order to discover the role and tasks content."""

    playbooks: list[str] = dspy.InputField()
    job: Job = dspy.OutputField()


root = rcav2.git.workspace_root.expanduser()


def read_file(path: str) -> str | None:
    """Read a file content, return None when there is an error"""
    print(f"[T] Reading file {path}")
    try:
        return (root / path).read_text()
    except Exception as e:
        print(f"{path}: read error {e}")
        return None


def find_file(glob: str) -> list[str]:
    """Return paths matching a glob applied on find results."""
    print(f"[T] Looking for file {glob}")
    return []


def make_agent():
    return dspy.ReAct(DSPyAnsibleOracle, tools=[read_file, find_file])


async def call_agent(agent: dspy.ReAct, plays: list[str], worker: Worker) -> Job:
    # Make the path relative to the workspace
    playbooks = list(map(lambda p: str(p)[len(str(root)) + 1 :], plays))

    await worker.emit(f"Calling AnsibleOracle with {playbooks}", "progress")
    result = await agent.acall(playbooks=plays)
    print(result)

    return result["job"]


async def main() -> None:
    """A test experiment"""
    import sys
    import json
    import rcav2.zuul
    import rcav2.model
    from rcav2.worker import CLIWorker

    job = sys.argv[1]
    export = json.load(open(".zuul-export.json"))
    info = rcav2.zuul.read_weeder_export(export)
    plays = await rcav2.zuul.get_job_playbooks(info, job)
    if not plays:
        print("Couldn't find job playbook")
        return

    rcav2.model.init_dspy()
    agent = make_agent()
    job_info = await call_agent(agent, plays, CLIWorker())
    print(job_info)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
