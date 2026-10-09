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

if __name__=='__main__': unittest.main()
