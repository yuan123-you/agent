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


def _production_ai_environment():
    import re
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / 'deploy/compose.production.yml').read_text(encoding='utf-8')
    section = re.search(r'(?ms)^  ai-service:\n(.*?)(?=^  [\w-]+:|\Z)', text).group(1)
    return {key: value.strip().strip("'\"") for key, value in
            re.findall(r'^      ([A-Z][A-Z0-9_]*):\s*(.+)$', section, flags=re.MULTILINE)}


def test_production_generator_upgrade_keeps_intent_and_embedding_seams():
    env = _production_ai_environment()
    assert env['LLM_CHAT_MODEL'] == 'qwen3.5:4b'
    assert env['LLM_API_BASE'] == 'http://ollama:11434/v1'
    assert env['LLM_INTENT_API_BASE'] == 'http://intent:11434/v1'
    assert env['LLM_INTENT_MODEL'] == 'qwen3:4b-instruct'
    assert env['EMBEDDING_MODEL'] == 'shaw/dmeta-embedding-zh' and env['EMBEDDING_DIM'] == '768'
    assert env['KB_STRUCTURED_OUTPUT'] == 'true'
    assert env['KB_RESPONSE_MODE'] == 'generate' and env['KB_LEGACY_MAX_TOKENS'] == 'true'


def test_production_cpu_generation_has_bounded_budget_below_existing_sse_deadline():
    env = _production_ai_environment()
    assert int(env['KB_ANSWER_TIMEOUT_S']) == 150
    assert int(env['LLM_CHAT_TIMEOUT_S']) >= int(env['KB_ANSWER_TIMEOUT_S'])
    assert int(env['LLM_INTENT_TIMEOUT_S']) + int(env['KB_ANSWER_TIMEOUT_S']) < int(env['CHAT_TIMEOUT_S']) < 300


def test_generation_deadlines_fit_actual_gateway_stream_and_idle_limits():
    import re
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    service=(root/'backend/src/main/java/com/aimall/backend/chat/ChatService.java').read_text(encoding='utf-8')
    client=(root/'backend/src/main/java/com/aimall/backend/chat/AiClient.java').read_text(encoding='utf-8')
    total=int(re.search(r'\.take\(java\.time\.Duration\.ofSeconds\((\d+)\)\)',service).group(1))
    idle=int(re.search(r'\.timeout\(Duration\.ofSeconds\((\d+)\)\)',client).group(1))
    env=_production_ai_environment()
    assert int(env['CHAT_TIMEOUT_S']) < total
    assert int(env['KB_ANSWER_TIMEOUT_S']) < idle


def test_generation_factory_does_not_inherit_model_file_topic_diversity_defaults(monkeypatch):
    config=SimpleNamespace(llm_api_base='http://ollama/v1',llm_api_key='ollama',
        llm_chat_model='candidate',temperature=.3,llm_chat_timeout_s=150,llm_reasoning_effort='none')
    monkeypatch.setattr(llm,'settings',config)
    with patch.object(llm,'ChatOpenAI') as constructor:
        llm.get_chat_llm()
        assert constructor.call_args.kwargs['presence_penalty']==0
        assert constructor.call_args.kwargs['frequency_penalty']==0

def test_production_embedding_weights_outlive_slow_answer_turns():
    env = _production_ai_environment()
    assert env["OLLAMA_KEEP_ALIVE"] == "24h"

def test_four_core_production_intent_does_not_allocate_four_parallel_contexts():
    import re
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "deploy/compose.production.yml").read_text(encoding="utf-8")
    section = re.search(r"(?ms)^  intent:\n(.*?)(?=^  [\w-]+:|\Z)", text).group(1)
    assert "OLLAMA_NUM_PARALLEL: '1'" in section
    assert "mem_limit: 5g" in section
