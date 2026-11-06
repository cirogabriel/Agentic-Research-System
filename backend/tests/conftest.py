from __future__ import annotations

import pytest
from fakes import FakeLLM

from ars.config import Settings
from ars.llm.budget import UsageTracker


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, openai_api_key="test-key", rerank_enabled=False, token_budget=100_000, max_iterations=3, max_subtasks=3)


@pytest.fixture
def tracker(settings: Settings) -> UsageTracker:
    return UsageTracker.from_settings(settings)


@pytest.fixture
def llm(tracker: UsageTracker) -> FakeLLM:
    return FakeLLM(tracker)


CORPUS = {
    "andes_subduction.md": "La placa de Nazca subduce bajo la placa Sudamericana y produce los terremotos de los Andes.",
    "andes_earthquake_history.md": "El terremoto de Valdivia de 1960 alcanzó magnitud 9,5 en Chile.",
}


@pytest.fixture
def corpus() -> dict[str, str]:
    return dict(CORPUS)
