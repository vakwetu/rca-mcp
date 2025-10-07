# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass


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

    def git_url(self, project: str) -> str | None:
        match self.kind:
            case "GitlabUrl" | "GithubUrl" | "GerritUrl":
                url = self.url.rstrip("/r").lstrip("https://").rstrip("/")
                return f"git@{url}:{project}.git"
            case "GitUrl":
                return f"{self.url.rstrip('/')}/{project}"
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

    def project_git(self, project_name: str) -> str | None:
        if project := self.projects.get(project_name):
            return self.providers[project.provider].git_url(project_name)
        else:
            return None
