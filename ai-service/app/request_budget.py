"""Trusted internal hop budgets; duration headers may shorten, never extend policy."""
import asyncio
import json
import logging

from app.resilience import DeadlineExceeded, RetryBudgetExhausted, budget_scope

logger=logging.getLogger('ai-service.budget')


class RequestBudgetMiddleware:
    def __init__(self,app,*,timeout_s=60,action_timeout_s=15,retry_tokens=6):
        self.app,self.timeout_s,self.action_timeout_s,self.retry_tokens=app,timeout_s,action_timeout_s,retry_tokens

    @staticmethod
    def _integer(headers,name,default):
        value=headers.get(name)
        if value is None:return default
        if len(value)>16 or not value.isascii() or not value.isdecimal():
            raise ValueError('invalid request budget')
        return int(value)

    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        if scope['type']!='http' or not path.startswith('/v1/'):
            return await self.app(scope,receive,send)
        headers={k.decode('latin-1').lower():v.decode('latin-1') for k,v in scope.get('headers',[])}
        maximum=self.action_timeout_s if path.startswith('/v1/action-workflows/') else self.timeout_s
        try:
            millis=min(int(maximum*1000),self._integer(headers,'x-request-timeout-ms',int(maximum*1000)))
            permits=min(self.retry_tokens,self._integer(headers,'x-request-retry-budget',self.retry_tokens))
        except ValueError:
            return await self._error(send,400,2001,'invalid request budget')
        if millis<=0:
            return await self._error(send,503,5002,'request deadline exhausted')
        started=False;finished=False;sse=False;timer=None
        async def tracked(message):
            nonlocal started,finished,sse
            if not finished and budget.remaining()<=0:
                raise DeadlineExceeded("late response after request deadline")
            if message['type']=='http.response.start':
                started=True
                sse=any(k.lower()==b'content-type' and v.lower().startswith(b'text/event-stream')
                        for k,v in message.get('headers',[]))
            final=message['type']=='http.response.body' and not message.get('more_body',False)
            await send(message)
            if final:
                finished=True
                # Foreground is complete. A separately budgeted BackgroundTask
                # must not inherit this response's cancellation timer.
                if timer is not None and not timer.expired():timer.reschedule(None)
        with budget_scope(millis/1000,retry_tokens=permits,inherit=False) as budget:
            try:
                async with asyncio.timeout(budget.remaining()) as timer:
                    await self.app(scope,receive,tracked)
            except (TimeoutError,DeadlineExceeded,RetryBudgetExhausted):
                logger.warning('request deadline/retry budget exhausted')
                if not started:
                    await self._error(send,503,5002,'request deadline or retry budget exhausted')
                elif not finished:
                    body=(b'event: error\ndata: {"code":5002,"message":"request deadline or retry budget exhausted"}\n\n'
                          if sse else b'')
                    await send({'type':'http.response.body','body':body,'more_body':False})

    @staticmethod
    async def _error(send,status,code,message):
        body=json.dumps({'code':code,'message':message}).encode()
        await send({'type':'http.response.start','status':status,
                    'headers':[(b'content-type',b'application/json'),(b'content-length',str(len(body)).encode())]})
        await send({'type':'http.response.body','body':body,'more_body':False})
