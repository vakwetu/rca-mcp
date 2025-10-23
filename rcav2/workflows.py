# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import json

from rcav2.env import Env
from rcav2.database import Engine
from rcav2.worker import Worker
from rcav2.agent.zuul import Job

import rcav2.logjuicer
import rcav2.zuul
import rcav2.agent.zuul
import rcav2.agent.predict
import rcav2.agent.react
from rcav2.opik_trace import create_trace_storage


def load_job_description_file(file_path: str) -> str | None:
    """Load additional job description from file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading job description file {file_path}: {e}")
        return None


async def job_from_model(env: Env, name: str, worker: Worker) -> Job | None:
    await worker.emit("Reading job plays...", event="progress")
    zuul_info = await rcav2.zuul.ensure_zuul_info(env)
    plays = await rcav2.zuul.get_job_playbooks(zuul_info, name)
    if not plays:
        await worker.emit(f"Couldn't find job {name}", event="error")
        return None
    else:
        await worker.emit("Analyzing job...", event="progress")
        agent = rcav2.agent.zuul.make_agent(worker)
        return await rcav2.agent.zuul.call_agent(agent, plays, worker)


async def job_from_db(db: Engine, job_name: str, worker: Worker) -> Job | None:
    if events := rcav2.database.get_job(db, job_name):
        await worker.emit("Found a description in the cache", event="progress")
        return rcav2.agent.zuul.Job.model_validate(
            list(filter(lambda ev: ev[0] == "job", json.loads(events)))[0][1]
        )
    return None


async def describe_job(
    env: Env,
    db: Engine | None,
    job_name: str,
    worker: Worker,
    job_description_file: str | None = None,
) -> Job | None:
    # Load additional job description from file if provided
    additional_description: str | None = None
    if job_description_file:
        additional_description = load_job_description_file(job_description_file)
        if additional_description:
            await worker.emit(
                f"Loaded additional job description from {job_description_file}",
                event="progress",
            )
        else:
            await worker.emit(
                f"Could not load job description from {job_description_file}",
                event="error",
            )

    if db:
        if job := await job_from_db(db, job_name, worker):
            # Append additional description if available
            if additional_description:
                job.description = f"{job.description}\n\nAdditional Context:\n{additional_description}"
            return job

    job = await job_from_model(env, job_name, worker)
    if job and additional_description:
        # Append additional description if available
        job.description = (
            f"{job.description}\n\nAdditional Context:\n{additional_description}"
        )
    elif not job and additional_description:
        # Create a job with just the additional description if no job was found
        from rcav2.agent.zuul import Job

        job = Job(description=additional_description, actions=[])

    return job


async def rca_predict(
    env: Env,
    db: Engine | None,
    url: str,
    worker: Worker,
    local_report_file: str | None = None,
    job_description_file: str | None = None,
) -> None:
    """A two step workflow with job description"""
    await worker.emit("predict", event="workflow")

    # Initialize Opik trace storage
    trace_storage = create_trace_storage(env)

    try:
        # Start trace
        await trace_storage.start_trace(url, "rca-predict", worker)

        # Fetch build errors
        await worker.emit("Fetching build errors...", event="progress")
        await trace_storage.start_span(
            "Error Report Fetching",
            {"url": url, "local_file": local_report_file},
            worker,
        )
        errors_report = await rcav2.logjuicer.get_report(
            env, url, worker, local_report_file
        )
        await trace_storage.end_span(
            {
                "error_count": sum(
                    len(logfile.errors) for logfile in errors_report.logfiles
                )
            },
            worker,
        )

        # Describe job
        await worker.emit(f"Describing job {errors_report.target}...", event="progress")
        await trace_storage.start_span(
            "Job Description",
            {
                "job_name": errors_report.target,
                "job_description_file": job_description_file,
            },
            worker,
        )
        job = await describe_job(
            env, db, errors_report.target, worker, job_description_file
        )
        if job:
            await worker.emit(job.model_dump(), event="job")
        await trace_storage.end_span({"job_found": job is not None}, worker)

        # Run RCA analysis
        await trace_storage.start_span("RCA Analysis", {"workflow": "predict"}, worker)
        rca_agent = rcav2.agent.predict.make_agent()
        report = await rcav2.agent.predict.call_agent(
            rca_agent, job, errors_report, worker, trace_storage
        )

        # Store error analysis in Opik
        await trace_storage.store_error_analysis(
            errors_report, report.description, worker
        )
        await trace_storage.end_span(
            {"analysis_complete": True, "result": report}, worker
        )
        await worker.emit(report.model_dump(), event="report")

        # End trace
        await trace_storage.end_trace({"workflow": "predict", "result": report}, worker)
    except Exception as e:
        env.log.error(f"RCA predict workflow failed: {e}")
        await worker.emit(f"RCA analysis failed: {e}", event="error")
        if trace_storage.is_available():
            await trace_storage.end_trace(
                {"error": str(e), "workflow": "predict"}, worker
            )
    finally:
        # Flush traces to Opik
        await trace_storage.flush_traces(worker)


async def rca_react(
    env: Env,
    db: Engine | None,
    url: str,
    worker: Worker,
    local_report_file: str | None = None,
    job_description_file: str | None = None,
) -> None:
    """A two step workflow using a ReAct module"""
    await worker.emit("react", event="workflow")

    # Initialize Opik trace storage
    trace_storage = create_trace_storage(env)

    try:
        # Start trace
        await trace_storage.start_trace(url, "rca-react", worker)

        # Fetch build errors
        await worker.emit("Fetching build errors...", event="progress")
        await trace_storage.start_span(
            "Error Report Fetching",
            {"url": url, "local_file": local_report_file},
            worker,
        )
        errors_report = await rcav2.logjuicer.get_report(
            env, url, worker, local_report_file
        )
        await trace_storage.end_span(
            {
                "error_count": sum(
                    len(logfile.errors) for logfile in errors_report.logfiles
                )
            },
            worker,
        )

        # Describe job
        await worker.emit(f"Describing job {errors_report.target}...", event="progress")
        await trace_storage.start_span(
            "Job Description",
            {
                "job_name": errors_report.target,
                "job_description_file": job_description_file,
            },
            worker,
        )
        job = await describe_job(
            env, db, errors_report.target, worker, job_description_file
        )
        if job:
            await worker.emit(job.model_dump(), event="job")
        await trace_storage.end_span({"job_found": job is not None}, worker)

        # Run RCA analysis with ReAct
        await trace_storage.start_span(
            "RCA Analysis (ReAct)", {"workflow": "react"}, worker
        )
        rca_agent = rcav2.agent.react.make_agent(errors_report, worker)
        report = await rcav2.agent.react.call_agent(
            rca_agent, job, errors_report, worker, trace_storage
        )

        # Store error analysis in Opik
        await trace_storage.store_error_analysis(
            errors_report, report.description, worker
        )
        await trace_storage.end_span(
            {"analysis_complete": True, "result": report}, worker
        )
        await worker.emit(report.model_dump(), event="report")

        # End trace
        await trace_storage.end_trace({"workflow": "react", "result": report}, worker)
    except Exception as e:
        env.log.error(f"RCA react workflow failed: {e}")
        await worker.emit(f"RCA analysis failed: {e}", event="error")
        if trace_storage.is_available():
            await trace_storage.end_trace(
                {"error": str(e), "workflow": "react"}, worker
            )
    finally:
        # Flush traces to Opik
        await trace_storage.flush_traces(worker)
