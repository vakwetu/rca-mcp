# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import asyncio
import unittest
from rcav2.worker import Pool, Job, Worker


class Dummy(Job):
    def __init__(self, url: str):
        self.url = url

    @property
    def job_key(self) -> str:
        return self.url

    async def run(self, worker: Worker):
        await worker.emit("starting...", event="log")
        for x in range(5):
            await asyncio.sleep(0.1)
            await worker.emit(f"performing step {x}...", event="log")
        await worker.emit("completed", event="status")


class TestPool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = Pool(2)

    async def asyncTearDown(self) -> None:
        await self.pool.stop()

    async def test_pool(self) -> None:
        await self.pool.submit(Dummy("test"))
        watcher = await self.pool.watch("test")
        for i in range(7):
            (ev, _) = await watcher.recv()
        self.assertEqual(ev, "status")
