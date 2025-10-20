# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

"""
Opik trace storage functionality for RCA analysis.
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import opik
    from opik import Opik, Trace, Span
except ImportError:
    opik = None
    Opik = None
    Trace = None
    Span = None

from rcav2.env import Env
from rcav2.worker import Worker
from rcav2.errors import Report
from rcav2.config import OPIK_API_KEY, OPIK_PROJECT_NAME


class OpikTraceStorage:
    """Handles trace storage to Opik backend."""

    def __init__(self, env: Env):
        self.env = env
        self.log = logging.getLogger("rcav2.opik_trace")
        self.client: Optional[Opik] = None
        self.current_trace: Optional[Trace] = None
        self.current_span: Optional[Span] = None

        # Initialize Opik client if available
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Opik client with API key from configuration."""
        if opik is None:
            self.log.warning("Opik SDK not available. Trace storage disabled.")
            return

        if not OPIK_API_KEY:
            self.log.warning("No Opik API key found. Set OPIK_API_KEY or LLM_GEMINI_KEY environment variable.")
            return

        try:
            self.client = Opik(
                api_key=OPIK_API_KEY,
                project_name=OPIK_PROJECT_NAME
            )
            self.log.info(f"Opik client initialized successfully for project: {OPIK_PROJECT_NAME}")
        except Exception as e:
            self.log.error(f"Failed to initialize Opik client: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if Opik trace storage is available."""
        return self.client is not None

    async def start_trace(self, build_url: str, job_name: str, worker: Worker) -> None:
        """Start a new trace for RCA analysis."""
        if not self.is_available():
            return

        try:
            trace_name = f"RCA Analysis - {job_name}"
            trace_input = {
                "build_url": build_url,
                "job_name": job_name,
                "analysis_type": "root_cause_analysis"
            }

            self.current_trace = self.client.trace(
                name=trace_name,
                input=trace_input
            )

            await worker.emit(f"Started Opik trace: {trace_name}", event="progress")
            self.log.info(f"Started trace: {trace_name}")

        except Exception as e:
            self.log.error(f"Failed to start trace: {e}")
            await worker.emit(f"Failed to start Opik trace: {e}", event="error")

    async def start_span(self, span_name: str, input_data: Dict[str, Any], worker: Worker) -> None:
        """Start a new span within the current trace."""
        if not self.is_available() or not self.current_trace:
            return

        try:
            self.current_span = self.current_trace.span(
                name=span_name,
                input=input_data
            )
            await worker.emit(f"Started Opik span: {span_name}", event="progress")
            self.log.info(f"Started span: {span_name}")
        except Exception as e:
            self.log.error(f"Failed to start span: {e}")
            await worker.emit(f"Failed to start Opik span: {e}", event="error")

    async def end_span(self, output_data: Dict[str, Any], worker: Worker) -> None:
        """End the current span with output data."""
        if not self.is_available() or not self.current_span:
            return

        try:
            self.current_span.end(output=output_data)
            await worker.emit("Ended Opik span", event="progress")
            self.log.info("Ended span")
            self.current_span = None
        except Exception as e:
            self.log.error(f"Failed to end span: {e}")
            await worker.emit(f"Failed to end Opik span: {e}", event="error")

    async def end_trace(self, final_output: Dict[str, Any], worker: Worker) -> None:
        """End the current trace with final output."""
        if not self.is_available() or not self.current_trace:
            return

        try:
            self.current_trace.end(output=final_output)
            await worker.emit("Ended Opik trace", event="progress")
            self.log.info("Ended trace")
            self.current_trace = None
        except Exception as e:
            self.log.error(f"Failed to end trace: {e}")
            await worker.emit(f"Failed to end Opik trace: {e}", event="error")

    async def store_error_analysis(self, report: Report, analysis_result: str, worker: Worker) -> None:
        """Store error analysis as a span."""
        if not self.is_available() or not self.current_trace:
            return

        try:
            # Create error analysis span
            error_span = self.current_trace.span(
                name="Error Analysis",
                input={
                    "error_count": sum(len(logfile.errors) for logfile in report.logfiles),
                    "logfiles": [logfile.source for logfile in report.logfiles],
                    "target": report.target
                }
            )

            # Add error details as metadata
            error_details = []
            for logfile in report.logfiles:
                for error in logfile.errors:
                    error_details.append({
                        "source": logfile.source,
                        "line": error.line,
                        "position": error.pos
                    })

            error_span.update(metadata={
                "error_details": error_details,
                "analysis_result": analysis_result
            })

            error_span.end(output={
                "analysis_complete": True,
                "errors_analyzed": len(error_details),
                "result": analysis_result
            })

            await worker.emit("Stored error analysis in Opik", event="progress")
            self.log.info("Stored error analysis")
        except Exception as e:
            self.log.error(f"Failed to store error analysis: {e}")
            await worker.emit(f"Failed to store error analysis: {e}", event="error")

    async def store_llm_interaction(self, prompt: str, response: str, model: str, usage: dict, worker: Worker) -> None:
        """Store LLM interaction details as a span."""
        if not self.is_available() or not self.current_trace:
            return

        try:
            # Create LLM interaction span
            llm_span = self.current_trace.span(
                name=f"LLM Interaction - {model}",
                input={
                    "prompt": prompt,
                    "model": model,
                    "prompt_length": len(prompt)
                }
            )

            llm_span.update(metadata={
                "usage": usage,
                "response_length": len(response)
            })

            llm_span.end(output={
                "response": response,
                "tokens_used": usage.get("total_tokens", 0),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)
            })

            await worker.emit(f"Stored LLM interaction for {model}", event="progress")
            self.log.info(f"Stored LLM interaction for {model}")
        except Exception as e:
            self.log.error(f"Failed to store LLM interaction: {e}")
            await worker.emit(f"Failed to store LLM interaction: {e}", event="error")

    async def flush_traces(self, worker: Worker) -> None:
        """Flush all pending traces to Opik."""
        if not self.is_available():
            return

        try:
            self.client.flush()
            await worker.emit("Flushed traces to Opik", event="progress")
            self.log.info("Flushed traces to Opik")
        except Exception as e:
            self.log.error(f"Failed to flush traces: {e}")
            await worker.emit(f"Failed to flush traces: {e}", event="error")


def create_trace_storage(env: Env) -> OpikTraceStorage:
    """Create an OpikTraceStorage instance."""
    return OpikTraceStorage(env)
