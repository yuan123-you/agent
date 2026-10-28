"""Regenerating a persisted failed turn must not append a duplicate human/tool turn."""
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from langgraph.checkpoint.memory import MemorySaver
from app.api.chat import ChatRequest, ChatMessage, build_state
from app.agent.state import AgentState
from langgraph.graph import StateGraph, START, END


def test_regeneration_replaces_failed_checkpoint_messages_and_preserves_entities():
    builder = StateGraph(AgentState)
    builder.add_node('echo', lambda s: {})
    builder.add_edge(START, 'echo'); builder.add_edge('echo', END)
    cp = MemorySaver(); graph = builder.compile(checkpointer=cp)
    cfg = {'configurable': {'thread_id': 'conv_734'}}
    graph.update_state(cfg, {'messages': [HumanMessage(content='之前的问题'), AIMessage(content='之前的回答'),
        HumanMessage(content='hello'), AIMessage(content='失败的片段')], 'active_entities': {'last_category': 'PHONE'}})
    req = ChatRequest(conversation_id=734, user_id=1, message='hello',
        history=[ChatMessage(role='USER', content='之前的问题'), ChatMessage(role='AI', content='之前的回答')],
        options={'regenerate': True})
    state = build_state(req, checkpointer=cp)
    assert isinstance(state['messages'][0], RemoveMessage)
    graph.update_state(cfg, state)
    messages = graph.get_state(cfg).values['messages']
    assert [m.content for m in messages] == ['之前的问题', '之前的回答', 'hello']
    assert state['active_entities']['last_category'] == 'PHONE'

async def test_timeout_is_a_failure_event_not_a_successful_fallback_answer(monkeypatch):
    import json
    from app.api import chat
    class TimedOutGraph:
        async def astream_events(self, *args, **kwargs):
            if False:
                yield None
            raise TimeoutError()
    class Request:
        async def is_disconnected(self): return False
    monkeypatch.setattr(chat, 'checkpointer', MemorySaver())
    monkeypatch.setattr(chat, 'graph', TimedOutGraph())
    response = await chat.chat_stream(ChatRequest(conversation_id=734, user_id=1, message='hello'), Request())
    events = []
    async for raw in response.body_iterator:
        lines = raw.strip().splitlines()
        events.append((lines[0].removeprefix('event: '), json.loads(lines[1].removeprefix('data: '))))
    assert not any(kind == 'done' for kind, _ in events)
    assert any(kind == 'error' and data['code'] == 5002 for kind, data in events)
    assert not any(kind == 'token' for kind, _ in events)
