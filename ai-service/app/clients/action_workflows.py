"""Single-attempt internal business callbacks for the native workflow.

Only the LangGraph execution node owns automatic retries. These methods are not
registered as LLM tools and never accept a caller-provided business receipt.
"""
import httpx
from app.agent.action_workflow import WorkflowRejected, WorkflowRetryable
from app.resilience import budget_headers, classify, parse_retry_after, run


class ActionWorkflowBackend:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _request(self, operation, body):
        try:
            async def attempt(timeout):
                return await self.client.post('/internal/tools/action-workflows/' + operation,
                                              json=body,timeout=timeout,headers=budget_headers())
            response = await run("action.callback." + operation,attempt,replay_safe=True,max_attempts=1,
                                 attempt_timeout_s=self.client.timeout.read or 3)
        except httpx.TransportError as error:
            raise WorkflowRetryable('business callback transport unavailable',retryable=classify(error)[0]) from error
        if response.status_code in {408,429,500,502,503,504}:
            raise WorkflowRetryable('business callback temporarily unavailable',
                                    retry_after_s=parse_retry_after(response.headers.get('Retry-After')))
        try:
            data = response.json()
        except ValueError as error:
            if response.is_error:
                raise WorkflowRejected(response.status_code, 'business callback rejected') from None
            raise WorkflowRetryable('business callback returned invalid JSON',retryable=False) from error
        if not isinstance(data, dict) or type(data.get('code')) is not int:
            if response.is_error:
                raise WorkflowRejected(response.status_code, 'business callback rejected')
            raise WorkflowRetryable('business callback returned invalid envelope',retryable=False)
        if data['code'] != 0:
            raise WorkflowRejected(data['code'], str(data.get('message') or 'business action rejected'))
        if response.is_error:
            raise WorkflowRejected(response.status_code, 'business callback rejected')
        if not isinstance(data.get('data'), dict):
            raise WorkflowRetryable('business callback returned no receipt',retryable=False)
        return data['data']

    async def snapshot(self, user_id, action_id):
        return await self._request('snapshot', {'userId': user_id, 'actionId': action_id})

    async def execute(self, user_id, action_id, approval):
        return await self._request('execute', {'userId': user_id, 'actionId': action_id, 'approval': approval})

    async def cancel(self, user_id, action_id):
        return await self._request('cancel', {'userId': user_id, 'actionId': action_id})
