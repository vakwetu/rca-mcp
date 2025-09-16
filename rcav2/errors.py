# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

"""
This module contains helper to pre-process a LogJuicer report.
"""

from dataclasses import dataclass


@dataclass
class Error:
    before: list[str]
    line: str
    pos: int
    after: list[str]


@dataclass
class LogFile:
    source: str
    errors: list[Error]


@dataclass
class Report:
    target: str
    logfiles: list[LogFile]


def read_source(source) -> str:
    """Convert absolute source url into a relative path.

    >>> read_source({'RawFile': {'Remote': [12, 'example.com/zuul/overcloud.log']}})
    'zuul/overcloud.log'
    """
    match source:
        case {"RawFile": {"Remote": [pos, path]}}:
            return path[pos:]
        case {"TarFile": [{"Remote": [pos, _]}, _, path]}:
            return path[pos:]
        case _:
            return f"Unknown source: {source}"


def read_target(target) -> str:
    """Convert a target description.

    >>> read_target({'Zuul': {'job_name': 'tox'}})
    'Zuul job named tox'
    """
    match target:
        case {"Zuul": build}:
            return f"Zuul job named {build['job_name']}"
        case _:
            return f"Unknown target: {target}"


def read_error(anomaly) -> Error:
    return Error(
        anomaly["before"],
        anomaly["anomaly"]["line"],
        anomaly["anomaly"]["pos"],
        anomaly["after"],
    )


def read_logfile(log_report) -> LogFile:
    return LogFile(log_report["source"], list(map(read_error, log_report["anomalies"])))


def json_to_report(report) -> Report:
    return Report(
        read_target(report["target"]), list(map(read_logfile, report["log_reports"]))
    )


def report_to_json(report: Report) -> dict:
    import dataclasses

    return dataclasses.asdict(report)
