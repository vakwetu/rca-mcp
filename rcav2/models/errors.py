# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

"""
This module contains helpers to pre-process a LogJuicer report.
"""

from pydantic import BaseModel


class LogSource(BaseModel):
    log_name: str
    log_url: str
    archive: bool


class Error(BaseModel):
    before: list[str]
    line: str
    pos: int
    after: list[str]


class LogFile(BaseModel):
    source: LogSource
    errors: list[Error]


class Report(BaseModel):
    target: str
    log_url: str | None
    logfiles: list[LogFile]


def read_source(source: dict) -> LogSource:
    """Convert absolute source url into a relative path.

    >>> read_source({'RawFile': {'Remote': [12, 'example.com/zuul/overcloud.log']}})
    LogSource(log_name='zuul/overcloud.log', log_url='example.com/zuul/overcloud.log', archive=False)
    """
    match source:
        case {"RawFile": {"Remote": [pos, url]}}:
            return LogSource(log_name=url[pos:], log_url=url, archive=False)
        case {"TarFile": [{"Remote": [_, tar_url]}, _, tar_name]}:
            return LogSource(log_name=tar_name, log_url=tar_url, archive=True)
        case _:
            return LogSource(
                log_name=f"Unknown source: {source}", log_url="", archive=False
            )


def read_target(target) -> str:
    """Convert a target description.

    >>> read_target({'Zuul': {'job_name': 'tox'}})
    'tox'
    """
    match target:
        case {"Zuul": build}:
            return build["job_name"]
        case _:
            return f"Unknown target: {target}"


def read_log_url(target) -> str | None:
    match target:
        case {"Zuul": build}:
            return build["log_url"]
        case _:
            return None


def read_error(anomaly: dict, source: dict) -> Error:
    """Creates an Error from an anomaly."""
    return Error(
        before=anomaly["before"],
        line=anomaly["anomaly"]["line"],
        pos=anomaly["anomaly"]["pos"],
        after=anomaly["after"],
    )


def read_logfile(log_report: dict, logjuicer_url: str | None = None) -> LogFile:
    source_json = log_report["source"]
    return LogFile(
        source=read_source(source_json),
        errors=[
            read_error(anomaly, source_json, logjuicer_url)
            for anomaly in log_report["anomalies"]
        ],
    )


def json_to_report(report: dict) -> Report:
    return Report(
        target=read_target(report["target"]),
        logfiles=list(map(read_logfile, report["log_reports"])),
        log_url=read_log_url(report["target"]),
    )


def report_to_json(report: Report) -> dict:
    return report.model_dump()
