"""Shared test fixtures."""

import os
import tempfile

import pytest

from synapsecode.config import SynapseConfig, load_config


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory and chdir into it."""
    original = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original)


@pytest.fixture
def default_config():
    """Return a default SynapseConfig."""
    return SynapseConfig()
