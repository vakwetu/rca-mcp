# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import asyncio
from dataclasses import dataclass

import rcav2.auth
from rcav2.env import Env


@dataclass
class JobInfo:
    name: str
    parent: str | None
    path: str
    project: str


@dataclass
class ProjectInfo:
    name: str
    branch: str
    provider: str


@dataclass
class ProviderInfo:
    name: str
    url: str
    kind: str

    def http_url(self, project: str, branch: str, path: str) -> str | None:
        def opendev():
            return f"https://opendev.org/{project}/src/branch/{branch}/{path}"

        match self.kind:
            case "GitlabUrl":
                return f"{self.url}/{project}/-/blob/{branch}/{path}"
            case "GithubUrl":
                return f"{self.url}/{project}/blob/{branch}/{path}"
            case "GerritUrl":
                if self.url == "https://review.opendev.org":
                    return opendev()
                else:
                    url = self.url.rstrip("/r")
                    return f"{url}/cgit/{project}/tree/{path}?h={branch}"
            case "GitUrl":
                if self.url == "https://opendev.org":
                    return opendev()
            case _:
                print(f"Unknown provider: {self}")
        return None


@dataclass
class ZuulInfo:
    jobs: dict[str, JobInfo]
    projects: dict[str, ProjectInfo]
    providers: dict[str, ProviderInfo]

    def job_url(self, job_name: str, path: str | None = None) -> str | None:
        if job := self.jobs.get(job_name):
            if not path:
                path = job.path
            project = self.projects[job.project]
            return self.providers[project.provider].http_url(
                job.project, project.branch, path
            )
        else:
            return None


async def fetch_weeder_export(env: Env) -> dict:
    """Fetch the raw weeder export"""
    from rcav2.config import SF_URL

    # Ensure we are authenticated, otherwise the redirection will fail to PUT
    await rcav2.auth.ensure_cookie(env)
    url = f"{SF_URL}/weeder/export"
    return (await env.httpx.get(url, auth=env.auth)).raise_for_status().json()


def read_weeder_export(export: dict) -> ZuulInfo:
    """Process the weeder export"""
    res = ZuulInfo({}, {}, {})
    for job, variants in export["jobs"].items():
        mains = filter(lambda v: v[0]["branch"] in ["main", "master"], variants)
        try:
            [loc, info] = list(mains)[0]
        except IndexError:
            continue
        project = loc["project"]
        project_name = project["project"]
        if project_name not in res.projects:
            provider = project["provider"]
            res.projects[project_name] = ProjectInfo(
                project_name, loc["branch"], provider
            )
            url = loc["url"]
            res.providers.setdefault(
                provider,
                ProviderInfo(provider, url["contents"].rstrip("/"), url["tag"]),
            )
        res.jobs[job] = JobInfo(job, info.get("parent"), loc["path"], project_name)
    return res


def print_job_url(info: ZuulInfo, job_name: str):
    job = info.jobs.get(job_name)
    if not job:
        print(f"Unknown job: {job_name}")
        return
    print(f"{job_name}: {info.job_url(job_name)}")
    if parent := job.parent:
        print_job_url(info, parent)


async def amain() -> None:
    import json
    import sys

    env = Env(True, ".cookie")
    try:
        export = json.load(open(".zuul-export.json"))
    except Exception:
        export = await fetch_weeder_export(env)
        json.dump(export, open(".zuul-export.json", "w"))

    info = read_weeder_export(export)
    match sys.argv:
        case [_, "url", job_name]:
            print_job_url(info, job_name)
        case _:
            print("usage: url job")


def main():
    asyncio.run(amain())
