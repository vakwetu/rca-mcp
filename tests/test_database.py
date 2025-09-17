# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import unittest
from sqlalchemy import select
from sqlalchemy.orm import Session

import rcav2.database


class TestDatabase(unittest.TestCase):
    def test_database(self) -> None:
        engine = rcav2.database.create("")
        report = rcav2.database.get(engine, "test")
        self.assertEqual(report, None)
        rcav2.database.set(engine, "test", "events")
        report = rcav2.database.get(engine, "test")
        self.assertEqual(report, "events")
