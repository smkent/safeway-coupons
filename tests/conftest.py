from typing import Iterable

import pytest
import responses


@pytest.fixture
def http_responses() -> Iterable[responses.RequestsMock]:
    with responses.RequestsMock() as resp_mock:
        yield resp_mock
