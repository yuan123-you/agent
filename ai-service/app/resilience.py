"""One-owner bounded HTTP retries. No payloads, credentials or URLs in retry telemetry."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import timezone
from email.utils import parsedate_to_datetime
import json
import logging
import math
import random
import ssl
from threading import Lock
from time import monotonic, time
from typing import Awaitable, Callable, TypeVar

import httpx

T = TypeVar('T')
logger = logging.getLogger('ai-service.resilience')
_sleep = asyncio.sleep


class DeadlineExceeded(TimeoutError):
    """No admissible attempt fits the remaining operation deadline."""


class RetryBudgetExhausted(RuntimeError):
    pass


class TransientFailure(Exception):
    def __init__(self, message, *, retry_after_s=None, retryable=True):
        super().__init__(message)
        self.retry_after_s = retry_after_s
        self.retryable = retryable


@dataclass
class _Ledger:
    remaining: int
    events: list[dict] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock,repr=False)

    def take_retry(self):
        with self.lock:
            if self.remaining<=0:
                return False
            self.remaining-=1
            return True


@dataclass
class RequestBudget:
    deadline: float
    ledger: _Ledger

    def remaining(self):
        return max(0.0, self.deadline - monotonic())

    @property
    def retry_tokens_remaining(self):
        return self.ledger.remaining

    @property
    def events(self):
        return self.ledger.events


_budget: ContextVar[RequestBudget | None] = ContextVar('retry_budget', default=None)
@dataclass
class _AttemptOwner:
    replay_prohibited: bool = False


_owner: ContextVar[_AttemptOwner | None] = ContextVar('retry_owner',default=None)


def current_budget():
    return _budget.get()


def _positive(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + ' must be finite and positive')
    return float(value)


@contextmanager
def budget_scope(timeout_s: float, retry_tokens: int = 6, *, inherit=True):
    timeout_s = _positive(timeout_s, 'timeout')
    if type(retry_tokens) is not int or not 0 <= retry_tokens <= 64:
        raise ValueError('retry permits must be an integer in [0,64]')
    parent = current_budget() if inherit else None
    deadline = monotonic() + timeout_s
    if parent:
        deadline = min(deadline, parent.deadline)
        ledger = parent.ledger
    else:
        ledger = _Ledger(retry_tokens)
    budget = RequestBudget(deadline, ledger)
    token = _budget.set(budget)
    owner_token = _owner.set(None) if not inherit else None
    try:
        yield budget
    finally:
        if owner_token is not None:
            _owner.reset(owner_token)
        _budget.reset(token)


def remaining_timeout(limit_s):
    limit_s = _positive(limit_s, 'timeout')
    budget = current_budget()
    remaining = min(limit_s, budget.remaining()) if budget else limit_s
    if remaining <= 0:
        raise DeadlineExceeded('request deadline exhausted')
    return remaining


def budget_headers():
    budget = current_budget()
    if budget is None:
        return {}
    return {'X-Request-Timeout-Ms': str(max(0, int(budget.remaining() * 1000))),
            'X-Request-Retry-Budget': str(budget.retry_tokens_remaining)}


def parse_retry_after(value, *, now=None):
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        return None
    value = value.strip()
    try:
        if value.isascii() and value.isdecimal():
            result = float(value)
        else:
            stamp = parsedate_to_datetime(value)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            result = max(0.0, stamp.timestamp() - (time() if now is None else now))
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, OverflowError, TypeError):
        return None


def classify(error):
    """Positive transient allowlist; permanent causes override adapter wrapping."""
    cause=error;seen=set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if getattr(cause,'_automatic_replay_prohibited',False):
            return False,'unsafe_replay',None
        if isinstance(cause,ssl.SSLError):
            return False,'tls_configuration',None
        if isinstance(cause,httpx.RemoteProtocolError) and str(cause) != "Server disconnected without sending a response.":
            return False,'malformed_http',None
        cause=cause.__cause__ or cause.__context__
    if isinstance(error,(DeadlineExceeded,RetryBudgetExhausted)):
        return False,'budget',None
    if isinstance(error,TransientFailure):
        return error.retryable,'transient' if error.retryable else 'protocol',error.retry_after_s
    if isinstance(error,httpx.HTTPStatusError):
        status=error.response.status_code
        return status in {408,429,500,502,503,504},'http_'+str(status),parse_retry_after(error.response.headers.get('Retry-After'))
    if isinstance(error,(httpx.TimeoutException,TimeoutError)):
        return True,'timeout',None
    if isinstance(error,httpx.RemoteProtocolError):
        # httpcore's explicit EOF-before-headers sentinel, verified against the
        # pinned HTTPX transport. Unknown/malformed protocol messages fail closed.
        return True,'disconnect_before_response',None
    if isinstance(error,httpx.NetworkError):
        return True,'transport',None
    return False,'permanent',None


def _event(budget, operation, attempt, outcome, *, category=None, wait_s=0):
    row = {'operation': operation, 'attempt': attempt, 'outcome': outcome,
           'category': category, 'wait_s': wait_s,
           'remaining_s': budget.remaining(), 'retry_tokens_remaining': budget.retry_tokens_remaining}
    budget.events.append(row)
    logger.info('outbound_attempt %s',json.dumps(row,separators=(',',':'),allow_nan=False),extra={'retry':row})


async def run(operation: str, call: Callable[[float], Awaitable[T]], *, replay_safe: bool,
              max_attempts=3, attempt_timeout_s=30, total_timeout_s=None,
              base_delay_s=.25, max_delay_s=2) -> T:
    if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
        raise ValueError('max_attempts must be in [1,10]')
    attempt_timeout_s = _positive(attempt_timeout_s, 'attempt timeout')
    for number in (base_delay_s,max_delay_s):
        if not math.isfinite(number) or number < 0:
            raise ValueError('backoff values must be finite and nonnegative')
    parent_owner=_owner.get()
    limit = 1 if parent_owner is not None or not replay_safe else max_attempts
    with budget_scope(total_timeout_s if total_timeout_s is not None else attempt_timeout_s) as budget:
        for attempt in range(1,limit + 1):
            remaining = remaining_timeout(attempt_timeout_s)
            _event(budget,operation,attempt,'attempt')
            attempt_owner=parent_owner if parent_owner is not None else _AttemptOwner()
            if not replay_safe:
                # Dispatch taints the entire owner, even if the write succeeds,
                # its acknowledgement is cancelled, or an adapter wraps an error.
                attempt_owner.replay_prohibited=True
            token = _owner.set(attempt_owner)
            try:
                async with asyncio.timeout(remaining):
                    value = await call(remaining)
                if budget.remaining() <= 0:
                    raise DeadlineExceeded('request deadline exhausted')
                opened_stream=isinstance(value,httpx.Response) and value.headers.get('content-type','').lower().startswith('text/event-stream')
                _event(budget,operation,attempt,'stream_open' if opened_stream else 'success')
                return value
            except asyncio.CancelledError:
                _event(budget,operation,attempt,'cancelled')
                raise
            except Exception as error:
                if attempt_owner.replay_prohibited:
                    try:
                        error._automatic_replay_prohibited=True
                    except (AttributeError,TypeError):
                        pass  # Owner taint remains authoritative for immutable errors.
                retryable, category, retry_after = classify(error)
                if attempt_owner.replay_prohibited:
                    retryable,category=False,'unsafe_replay'
                _event(budget,operation,attempt,'failure',category=category)
                if budget.remaining() <= 0:
                    raise DeadlineExceeded('request deadline exhausted') from error
                if not retryable or attempt >= limit:
                    raise
                cap = min(max_delay_s,base_delay_s * 2 ** (attempt - 1))
                if retry_after is not None:
                    if not math.isfinite(retry_after) or retry_after < 0 or retry_after > max_delay_s:
                        _event(budget,operation,attempt,'retry_after_refused',category=category)
                        raise
                    # Spread throttled callers above the server's minimum too,
                    # while keeping the complete wait inside the configured cap.
                    delay = retry_after + random.uniform(0,min(cap,max_delay_s-retry_after))
                else:
                    delay = random.uniform(0,cap)
                if delay + .001 >= budget.remaining():
                    _event(budget,operation,attempt,'deadline_refused',category=category)
                    raise DeadlineExceeded('no retry fits remaining deadline') from error
                if not budget.ledger.take_retry():
                    _event(budget,operation,attempt,'permits_exhausted',category=category)
                    raise RetryBudgetExhausted('request retry permits exhausted') from error
                _event(budget,operation,attempt,'retry_wait',category=category,wait_s=delay)
                try:
                    async with asyncio.timeout(budget.remaining()):
                        await _sleep(delay)
                except TimeoutError as timeout:
                    raise DeadlineExceeded('deadline exhausted during retry backoff') from timeout
            finally:
                _owner.reset(token)
    raise AssertionError('unreachable retry state')


class _DeadlineStream(httpx.AsyncByteStream):
    def __init__(self,stream,budget):
        self.stream,self.budget=stream,budget

    async def __aiter__(self):
        iterator=self.stream.__aiter__()
        while True:
            remaining=self.budget.remaining()
            if remaining<=0:
                raise DeadlineExceeded("accepted stream deadline exhausted")
            try:
                async with asyncio.timeout(remaining):
                    chunk=await anext(iterator)
            except StopAsyncIteration:
                if self.budget.remaining()<=0:
                    raise DeadlineExceeded("late stream EOF after deadline")
                return
            except TimeoutError as error:
                raise DeadlineExceeded("accepted stream deadline exhausted") from error
            if self.budget.remaining()<=0:
                raise DeadlineExceeded("late stream chunk after deadline")
            yield chunk

    async def aclose(self):
        await self.stream.aclose()


class ResilientAsyncTransport(httpx.AsyncBaseTransport):
    """SDK retry owner: JSON responses may retry; accepted SSE never replays."""
    def __init__(self, operation, *, replay_safe, timeout_s, transport=None, max_attempts=3):
        self.operation, self.replay_safe = operation, replay_safe
        self.timeout_s, self.max_attempts = timeout_s,max_attempts
        self.transport = transport if transport is not None else httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        async def attempt(timeout):
            previous = request.extensions.get('timeout',{})
            request.extensions['timeout'] = {name: min(timeout,previous[name]) if previous.get(name) is not None else timeout
                for name in ('connect','read','write','pool')}
            response = await self.transport.handle_async_request(request)
            response.request = request
            try:
                response.raise_for_status()
                if response.headers.get('content-type','').lower().startswith('text/event-stream'):
                    # Once accepted, even a future outer wrapper may not replay it.
                    owner=_owner.get()
                    if owner is not None:owner.replay_prohibited=True
                    if not response.is_stream_consumed:
                        response.stream=_DeadlineStream(response.stream,current_budget())
                else:
                    await response.aread()
                return response
            except BaseException:
                await response.aclose()
                raise
        replay_safe = self.replay_safe and isinstance(request.stream,httpx.ByteStream)
        return await run(self.operation,attempt,replay_safe=replay_safe,max_attempts=self.max_attempts,
                         attempt_timeout_s=self.timeout_s)

    async def aclose(self):
        await self.transport.aclose()
