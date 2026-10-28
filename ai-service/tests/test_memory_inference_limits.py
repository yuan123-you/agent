from unittest.mock import AsyncMock,MagicMock,patch
from langchain_core.messages import AIMessage
from app.clients import llm
from app.agent import memory


def test_classification_token_limit_does_not_truncate_long_term_memory_json():
    with patch.object(llm,'ChatOpenAI') as factory:
        llm.get_intent_llm(classification=False)
        assert factory.call_args.kwargs.get('max_tokens') is None
        llm.get_intent_llm()
        assert factory.call_args.kwargs['max_tokens']==llm.settings.llm_intent_max_tokens


async def test_memory_extraction_explicitly_uses_nonclassification_output_budget(monkeypatch):
    model=MagicMock();model.ainvoke=AsyncMock(return_value=AIMessage(content='[{"category":"PREFERENCE","key":"feature","value":"摄影"}]'))
    factory=MagicMock(return_value=model)
    monkeypatch.setattr(memory,'get_intent_llm',factory)
    result=await memory.extract_memories_with_llm('我比较喜欢摄影','可以考虑适合拍照的手机。')
    assert result and result[0]['value']=='摄影'
    factory.assert_called_once_with(classification=False)

async def test_memory_inference_keeps_user_facts_but_not_program_owned_url_transport(monkeypatch):
    user='我更喜欢拍照好的手机，预算3000。'
    url='https://example.com/source?tracking='+('long-value-'*100)
    ai='已经根据真实商品说明了拍照特点。\n\n参考来源：\n[1. 资料标题]('+url+')'
    model=MagicMock();model.ainvoke=AsyncMock(return_value=AIMessage(content='[]'))
    monkeypatch.setattr(memory,'get_intent_llm',MagicMock(return_value=model))
    await memory.extract_memories_with_llm(user,ai)
    text=model.ainvoke.call_args.args[0][-1].content
    assert user in text and '拍照特点' in text and '资料标题' in text
    assert url not in text
