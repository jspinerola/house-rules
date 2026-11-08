import os

import pytest

from contracts.models import LLMResult

from app import registry


@pytest.mark.parametrize("mode", ["stub", pytest.param("grok", marks=pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_GROK"), reason="live Grok runs only with RUN_LIVE_GROK=1"))])
def test_llm_contract(use, mode):
    use(llm=mode)
    out = registry.get("llm").chat([{"role": "system", "content": "FLOW:couch"},
                                    {"role": "user", "content": "DRAFT: hello there"}])
    assert isinstance(out, LLMResult) and out.text
