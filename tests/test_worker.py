# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import asyncio
import unittest
from rcav2.worker import Pool, Dummy


class TestPool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = Pool(2)

    async def asyncTearDown(self) -> None:
        await self.pool.stop()

    async def test_pool(self) -> None:
        await self.pool.submit(Dummy("test"))
        await asyncio.sleep(1)
        job = self.pool.completed.get("test")
        self.assertIsNotNone(job)
