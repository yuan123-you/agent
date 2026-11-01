"""Unsafe dispatches must prohibit replay by any enclosing retry owner."""
import asyncio

import pytest

from app.resilience import TransientFailure, run


@pytest.mark.asyncio
async def test_successful_unsafe_write_is_not_replayed_after_a_later_transient_failure():
    effects = []

    async def write(timeout):
        effects.append("committed")
        return "receipt"

    async def outer(timeout):
        await run("unsafe.write", write, replay_safe=False)
        raise TransientFailure("later read failed")

    with pytest.raises(TransientFailure):
        await run("safe.outer", outer, replay_safe=True, max_attempts=3,
                  attempt_timeout_s=1, base_delay_s=0, max_delay_s=0)

    assert effects == ["committed"], "A successful unsafe write must taint its enclosing retry owner"


@pytest.mark.asyncio
async def test_outer_attempt_timeout_does_not_replay_a_cancelled_unsafe_write():
    effects = []
    cancellations = []
    stalled_acknowledgement = asyncio.Event()

    async def write(timeout):
        effects.append("committed")
        try:
            await stalled_acknowledgement.wait()
        except asyncio.CancelledError:
            cancellations.append("cancelled")
            raise

    async def outer(timeout):
        return await run("unsafe.write", write, replay_safe=False, attempt_timeout_s=2)

    with pytest.raises(TimeoutError):
        await run("safe.outer", outer, replay_safe=True, max_attempts=3,
                  attempt_timeout_s=.02, total_timeout_s=2,
                  base_delay_s=0, max_delay_s=0)

    assert effects == ["committed"], "Cancelling an unsafe write must not permit an outer replay"
    assert cancellations == ["cancelled"]


@pytest.mark.asyncio
async def test_wrapping_an_unsafe_write_failure_does_not_restore_replay_permission():
    effects = []

    async def write(timeout):
        effects.append("committed")
        raise TransientFailure("acknowledgement lost")

    async def outer(timeout):
        try:
            return await run("unsafe.write", write, replay_safe=False)
        except TransientFailure as error:
            raise TransientFailure("adapter unavailable") from error

    with pytest.raises(TransientFailure):
        await run("safe.outer", outer, replay_safe=True, max_attempts=3,
                  attempt_timeout_s=1, base_delay_s=0, max_delay_s=0)

    assert effects == ["committed"], "Exception wrapping must not erase unsafe-dispatch taint"
