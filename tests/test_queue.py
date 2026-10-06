import asyncio
import threading
import time

import pytest

from core.processing_queue import ProcessingQueue, QueueFullError


def test_submit_returns_before_slow_work_finishes():
    async def scenario():
        queue = ProcessingQueue(max_workers=1, max_queue_size=2)
        await queue.start()
        finished = asyncio.Event()

        def slow():
            time.sleep(0.4)
            return "done"

        async def on_success(result):
            assert result == "done"
            finished.set()

        started = time.perf_counter()
        await queue.submit(slow, on_success=on_success)
        assert time.perf_counter() - started < 0.2
        await asyncio.wait_for(finished.wait(), timeout=2)
        await queue.stop()

    asyncio.run(scenario())


def test_queue_rejects_work_when_full():
    async def scenario():
        queue = ProcessingQueue(max_workers=1, max_queue_size=1)
        await queue.start()
        release = threading.Event()

        def block():
            release.wait(2)
            return "ok"

        await queue.submit(block)
        await asyncio.sleep(0.05)
        await queue.submit(lambda: "queued")
        with pytest.raises(QueueFullError):
            await queue.submit(lambda: "overflow")
        release.set()
        await queue.stop()

    asyncio.run(scenario())
