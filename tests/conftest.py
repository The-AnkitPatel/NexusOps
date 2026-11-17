"""Shared fixtures: build a fresh enterprise DB once per test session."""

from __future__ import annotations

import pytest

from data.init_db import initialize_database


@pytest.fixture(scope="session", autouse=True)
def _init_database() -> None:
    initialize_database()
