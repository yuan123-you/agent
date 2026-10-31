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
            self.assertEqual(constructor.call_args.kwargs.get('max_tokens'),128)
            self.assertEqual(constructor.call_args.kwargs.get('max_retries'),0)

if __name__=='__main__': unittest.main()


def test_intent_endpoint_is_independent_without_changing_generation(monkeypatch):
    config = SimpleNamespace(
        llm_api_base='http://generation:11434/v1', llm_api_key='generation-key',
        llm_intent_api_base='http://intent:11434/v1', llm_intent_api_key='intent-key',
        llm_chat_model='existing-model', llm_intent_model='candidate-model',
        temperature=0.3, llm_reasoning_effort='none', llm_chat_timeout_s=60,
        llm_intent_timeout_s=30,
    )
    monkeypatch.setattr(llm, 'settings', config)
    with patch.object(llm, 'ChatOpenAI') as constructor:
        llm.get_chat_llm()
        assert constructor.call_args.kwargs['base_url'] == config.llm_api_base
        assert constructor.call_args.kwargs['api_key'] == config.llm_api_key
        for classification in (True, False):
            llm.get_intent_llm(classification=classification)
            assert constructor.call_args.kwargs['base_url'] == config.llm_intent_api_base
            assert constructor.call_args.kwargs['api_key'] == config.llm_intent_api_key
            assert constructor.call_args.kwargs['model'] == config.llm_intent_model


def test_empty_intent_endpoint_settings_reuse_existing_provider(monkeypatch):
    config = SimpleNamespace(
        llm_api_base='http://generation:11434/v1', llm_api_key='generation-key',
        llm_intent_api_base='', llm_intent_api_key='',
        llm_intent_model='existing-model', llm_reasoning_effort=None, llm_intent_timeout_s=30,
    )
    monkeypatch.setattr(llm, 'settings', config)
    with patch.object(llm, 'ChatOpenAI') as constructor:
        llm.get_intent_llm()
        assert constructor.call_args.kwargs['base_url'] == config.llm_api_base
        assert constructor.call_args.kwargs['api_key'] == config.llm_api_key
