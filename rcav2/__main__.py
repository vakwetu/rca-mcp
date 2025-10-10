# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import argparse
import asyncio

import rcav2.logjuicer
import rcav2.env
import rcav2.model
import rcav2.agent.rca
import rcav2.zuul
from rcav2.config import COOKIE_FILE
from rcav2.worker import CLIWorker


def usage():
    parser = argparse.ArgumentParser(description="Root Cause Analysis (RCA)")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--local-logjuicer", action="store_true")
    parser.add_argument("URL", help="The build URL")
    return parser.parse_args()


async def run(args, env: rcav2.env.Env):
    # Fetch the error report from logjuicer
    if args.local_logjuicer:
        report = await rcav2.logjuicer.get_report(env, args.URL)
    else:
        report = await rcav2.logjuicer.get_remote_report(env, args.URL, None)
    with open(".report.json", "w") as f:
        f.write(rcav2.logjuicer.dump_report(report))

    # Prepare dspy
    rcav2.model.init_dspy()
    worker = CLIWorker()

    # Describe the job...
    zuul_info = await rcav2.zuul.ensure_zuul_info(env)
    plays = await rcav2.zuul.get_job_playbooks(zuul_info, report.target)
    zuul_agent = rcav2.agent.zuul.make_agent(worker)
    job = await rcav2.agent.zuul.call_agent(zuul_agent, plays, worker)

    # Produce the RCA
    rca_agent = rcav2.agent.rca.make_agent()
    result = await rcav2.agent.rca.call_agent(rca_agent, job, report, worker)
    print(result)


async def amain():
    args = usage()
    env = rcav2.env.Env(args.debug, cookie_path=COOKIE_FILE)
    try:
        await run(args, env)
    finally:
        env.close()


def main():
    asyncio.run(amain())
