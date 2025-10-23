# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import argparse
import asyncio

import rcav2.env
import rcav2.model
import rcav2.workflows
from rcav2.config import COOKIE_FILE
from rcav2.worker import CLIWorker


def usage():
    parser = argparse.ArgumentParser(description="Root Cause Analysis (RCA)")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--workflow")
    parser.add_argument(
        "--local-report", help="Path to local logjuicer JSON report file"
    )
    parser.add_argument(
        "--job-description", help="Path to additional job description file"
    )
    parser.add_argument(
        "URL", nargs="?", help="The build URL (optional when using --local-report)"
    )
    return parser.parse_args()


async def amain() -> None:
    args = usage()

    # Validate arguments
    if not args.local_report and not args.URL:
        print("Error: Either --local-report or URL must be provided")
        return

    env = rcav2.env.Env(args.debug, cookie_path=COOKIE_FILE)
    try:
        # Prepare dspy
        rcav2.model.init_dspy()
        worker = CLIWorker()

        # Run workflow...
        match args.workflow:
            case None | "predict":
                await rcav2.workflows.rca_predict(
                    env, None, args.URL, worker, args.local_report, args.job_description
                )
            case "react":
                await rcav2.workflows.rca_react(
                    env, None, args.URL, worker, args.local_report, args.job_description
                )
            case "predict-no-job":
                print("NotImplemented")
    finally:
        env.close()


def main():
    asyncio.run(amain())
