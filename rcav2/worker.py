# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

"""
This module defines a Pool object to manage job pub/sub
"""

import asyncio
from abc import ABCMeta, abstractmethod


class Watcher:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def send(self, message: tuple[str, str]):
        await self.queue.put(message)

    async def recv(self) -> tuple[str, str]:
        event = await self.queue.get()
        self.queue.task_done()
        return event


class Worker:
    """A worker process that can be watched"""

    def __init__(self) -> None:
        self.watchers: list[Watcher] = []
        self.history: list[tuple[str, str]] = []

    async def emit(self, message: str, event: str) -> None:
        item = (event, message)
        self.history.append(item)
        for watcher in self.watchers:
            await watcher.send(item)

    async def add_watcher(self, watcher: Watcher):
        # Send past message...
        for item in self.history:
            await watcher.send(item)
        self.watchers.append(watcher)


class Job(metaclass=ABCMeta):
    @abstractmethod
    async def run(self, worker: Worker): ...

    @property
    @abstractmethod
    def job_key(self) -> str: ...


class Pool:
    """Pool of workers to manage pub/sub."""

    # https://docs.python.org/3/library/asyncio-queue.html#examples
    def __init__(self, max_worker: int):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pending: dict[str, tuple[Worker, Job]] = dict()
        self.completed: dict[str, Job] = dict()  # TODO: store this in a database
        self.workers = []
        for i in range(max_worker):
            task = asyncio.create_task(self.worker())
            self.workers.append(task)

    async def stop(self):
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

    async def submit(self, job: Job) -> str:
        key = job.job_key
        if self.completed.get(key):
            return "COMPLETED"
        else:
            if not self.pending.get(key):
                worker_job = (Worker(), job)
                self.pending[key] = worker_job
                await self.queue.put(worker_job)
            return "PENDING"

    async def watch(self, key: str) -> Watcher | None:
        if self.pending.get(key):
            watcher = Watcher()
            await self.pending[key][0].add_watcher(watcher)
            return watcher
        else:
            return None

    async def worker(self):
        while True:
            (worker, job) = await self.queue.get()
            key = job.job_key
            await job.run(worker)
            self.queue.task_done()
            self.completed[key] = job
            del self.pending[key]


class Dummy(Job):
    def __init__(self, url: str):
        self.url = url

    @property
    def job_key(self) -> str:
        return self.url

    async def run(self, worker: Worker):
        await worker.emit("log", "starting...")
        for x in range(5):
            await asyncio.sleep(0.1)
            await worker.emit("log", f"performing step {x}...")
        await worker.emit("completed", "done!")
