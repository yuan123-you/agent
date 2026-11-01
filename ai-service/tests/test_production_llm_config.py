import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app.clients import llm

class ProductionLlmConfigTests(unittest.TestCase):
    def test_production_can_disable_thinking_and_increase_cpu_timeouts(self):
        config=SimpleNamespace(llm_api_base='http://ollama:11434/v1',llm_api_key='ollama',llm_chat_model='qwen3.5:4b',llm_intent_model='qwen3.5:4b',temperature=0.3,llm_reasoning_effort='none',llm_chat_timeout_s=120,llm_intent_timeout_s=60)
        with patch.object(llm,'settings',config), patch.object(llm,'ChatOpenAI') as constructor:
            llm.get_chat_llm()
            self.assertEqual(constructor.call_args.kwargs.get('reasoning_effort'),'none')
            self.assertEqual(constructor.call_args.kwargs['timeout'],120)
            llm.get_intent_llm()
            self.assertEqual(constructor.call_args.kwargs.get('reasoning_effort'),'none')
            self.assertEqual(constructor.call_args.kwargs['timeout'],60)
            self.assertEqual(constructor.call_args.kwargs.get('max_tokens'),64)
            self.assertEqual(constructor.call_args.kwargs.get('max_retries'),0)

if __name__=='__main__': unittest.main()


def test_native_embedding_factory_respects_small_cpu_batch_limit(monkeypatch):
    config = SimpleNamespace(ollama_keep_alive="24h", ollama_num_ctx=2048,
        ollama_num_gpu=0, ollama_embed_batch_size=2)
    monkeypatch.setattr(llm,"settings",config)
    with patch.object(llm,"OllamaEmbeddings") as constructor:
        llm._make_embeddings("http://embeddings:11434", "", "shaw/dmeta-embedding-zh", provider="ollama",dimensions=768)
        assert constructor.call_args.kwargs["max_batch_size"] == 2
        assert constructor.call_args.kwargs["keep_alive"] == "24h"


def test_embedding_batch_configuration_rejects_zero_or_unbounded_values():
    import pytest
    from app.config import Settings
    for value in (0, 17):
        with pytest.raises(ValueError):
            Settings(_env_file=None, ollama_embed_batch_size=value)
