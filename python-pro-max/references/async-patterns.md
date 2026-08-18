# Async Programming Patterns

## Basic Async/Await

```python
import asyncio
from collections.abc import Coroutine
from pydantic import BaseModel

# Model the response shape instead of returning a bare dict
class FetchResult(BaseModel):
    """Outcome of a single fetch."""

    url: str
    status: str

# Basic async function
async def fetch_data(url: str) -> FetchResult:
    """Fetch data for a URL (simulated I/O)."""
    await asyncio.sleep(1)  # Simulate I/O
    return FetchResult(url=url, status="ok")

# Running async code
async def main() -> None:
    """Run the example fetch."""
    result = await fetch_data("https://api.example.com")
    print(result)

if __name__ == "__main__":
    asyncio.run(main())

# Multiple concurrent operations
async def fetch_all(urls: list[str]) -> list[FetchResult]:
    """Fetch every URL concurrently."""
    tasks = [fetch_data(url) for url in urls]
    return await asyncio.gather(*tasks)

# Error handling with gather
async def safe_fetch_all(urls: list[str]) -> list[FetchResult | None]:
    """Fetch every URL concurrently, returning None for failures."""
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r if not isinstance(r, Exception) else None for r in results]
```

## Task Groups (Python 3.11+)

```python
from asyncio import TaskGroup

# Task groups for structured concurrency
async def process_batch(items: list[int]) -> list[int]:
    """Process a batch of items as a structured task group."""
    results: list[int] = []

    async with TaskGroup() as tg:
        tasks = [tg.create_task(process_item(item)) for item in items]

    # All tasks complete before this line
    return [task.result() for task in tasks]

# Error handling with TaskGroup
async def robust_processing(items: list[str]) -> tuple[list[str], list[Exception]]:
    """Process items, collecting results and errors separately."""
    results: list[str] = []
    errors: list[Exception] = []

    try:
        async with TaskGroup() as tg:
            for item in items:
                tg.create_task(process_item_safe(item))
    except ExceptionGroup as eg:
        for exc in eg.exceptions:
            errors.append(exc)

    return results, errors
```

## Async Context Managers

```python
from typing import Self
from collections.abc import AsyncIterator

class AsyncDatabaseConnection:
    """Async context manager around a database connection."""

    url: str
    _conn: Connection | None

    def __init__(self, url: str) -> None:
        """Initialize the AsyncDatabaseConnection instance."""
        self.url = url
        self._conn = None

    async def __aenter__(self) -> Self:
        """Enter the async context."""
        self._conn = await connect(self.url)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the async context."""
        if self._conn:
            await self._conn.close()

    async def query(self, sql: str) -> list[dict[str, Any]]:
        """Run a SQL query, returning raw rows (a generic, schema-agnostic handler)."""
        if not self._conn:
            message = "Not connected"
            raise RuntimeError(message)
        return await self._conn.execute(sql)

# Usage — query() returns raw rows; the util parses them into model instances
async def get_users() -> list[User]:
    """Fetch all users via a managed connection."""
    async with AsyncDatabaseConnection("postgresql://...") as db:
        rows = await db.query("SELECT * FROM users")
        return [User(**row) for row in rows]

# Async context manager with contextlib
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_session() -> AsyncIterator[Session]:
    """Yield a session, committing on success and rolling back on error."""
    session = await create_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

## Async Generators

```python
from collections.abc import AsyncIterator

# Async generator for streaming data
async def read_lines(filepath: str) -> AsyncIterator[str]:
    """Yield stripped lines from a file."""
    async with aiofiles.open(filepath) as f:
        async for line in f:
            yield line.strip()

# Process stream
async def process_file(filepath: str) -> int:
    """Process each line of a file and return the count."""
    count = 0
    async for line in read_lines(filepath):
        await process_line(line)
        count += 1
    return count

# Async generator with cleanup
async def fetch_paginated(url: str) -> AsyncIterator[Item]:
    """Yield items from a paginated endpoint, parsed into models, until exhausted."""
    page = 1
    session = await create_session()
    try:
        while True:
            rows = await session.get(f"{url}?page={page}")
            if not rows:
                break
            for row in rows:
                yield Item(**row)  # validate each raw row into a model
            page += 1
    finally:
        await session.close()
```

## Async Comprehensions

```python
# Async list comprehension
async def fetch_all_users(user_ids: list[int]) -> list[User]:
    """Collect users from an async source into a list."""
    return [user async for user in fetch_users(user_ids)]

# Async dict comprehension
async def build_user_map(user_ids: list[int]) -> dict[int, User]:
    """Build an id-to-user map from an async source."""
    return {
        user.id: user
        async for user in fetch_users(user_ids)
    }

# Conditional async comprehension
async def get_active_users(user_ids: list[int]) -> list[User]:
    """Collect only the active users from an async source."""
    return [
        user
        async for user in fetch_users(user_ids)
        if user.is_active
    ]
```

## Synchronization Primitives

```python
import asyncio

# Lock for critical sections
class SharedResource:
    """Resource guarded by a lock for safe concurrent updates."""

    _lock: asyncio.Lock
    _data: dict[str, int]

    def __init__(self) -> None:
        """Initialize the SharedResource instance."""
        self._lock = asyncio.Lock()
        self._data = {}

    async def update(self, key: str, value: int) -> None:
        """Atomically add a value under a key."""
        async with self._lock:
            # Critical section
            current = self._data.get(key, 0)
            await asyncio.sleep(0.1)  # Simulate processing
            self._data[key] = current + value

# Semaphore for rate limiting
class RateLimiter:
    """Bound concurrency with a semaphore."""

    _semaphore: asyncio.Semaphore

    def __init__(self, max_concurrent: int) -> None:
        """Initialize the RateLimiter instance."""
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def process(self, item: str) -> str:
        """Process an item within the concurrency limit."""
        async with self._semaphore:
            return await expensive_operation(item)

# Event for coordination
class AsyncWorker:
    """Worker coordinated by ready/shutdown events."""

    _ready: asyncio.Event
    _shutdown: asyncio.Event

    def __init__(self) -> None:
        """Initialize the AsyncWorker instance."""
        self._ready = asyncio.Event()
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        """Initialize, signal readiness, then wait for shutdown."""
        # Initialization
        await self._initialize()
        self._ready.set()

        # Wait for shutdown
        await self._shutdown.wait()

    async def wait_ready(self) -> None:
        """Block until the worker is ready."""
        await self._ready.wait()

    def stop(self) -> None:
        """Signal the worker to shut down."""
        self._shutdown.set()
```

## Async Queue Patterns

```python
from asyncio import Queue

# Producer-consumer pattern
async def producer(queue: Queue[int], n: int) -> None:
    """Put n items onto the queue."""
    for i in range(n):
        await queue.put(i)
        await asyncio.sleep(0.1)

async def consumer(queue: Queue[int], name: str) -> None:
    """Consume and process items from the queue until cancelled."""
    while True:
        item = await queue.get()
        try:
            await process_item(item)
        finally:
            queue.task_done()

async def run_pipeline(num_items: int, num_workers: int) -> None:
    """Run a producer and pool of consumers to completion."""
    queue: Queue[int] = Queue(maxsize=10)

    # Start producer and consumers
    async with TaskGroup() as tg:
        tg.create_task(producer(queue, num_items))
        for i in range(num_workers):
            tg.create_task(consumer(queue, f"worker-{i}"))

        # Wait for all items to be processed
        await queue.join()
```

## Async Timeouts

```python
# Timeout for single operation
async def fetch_with_timeout(url: str, timeout: float) -> FetchResult | None:
    """Fetch a URL, returning None on timeout."""
    try:
        async with asyncio.timeout(timeout):
            return await fetch_data(url)
    except TimeoutError:
        return None

# Timeout for multiple operations
async def fetch_all_with_timeout(
    urls: list[str],
    timeout: float
) -> list[FetchResult | None]:
    """Fetch all URLs, returning Nones if the batch times out."""
    try:
        async with asyncio.timeout(timeout):
            return await fetch_all(urls)
    except TimeoutError:
        return [None] * len(urls)
```

## Background Tasks

```python
from asyncio import create_task, Task

class BackgroundTaskManager:
    """Track background tasks for coordinated shutdown."""

    _tasks: set[Task[None]]

    def __init__(self) -> None:
        """Initialize the BackgroundTaskManager instance."""
        self._tasks = set()

    def create_task(self, coro: Coroutine[None, None, None]) -> Task[None]:
        """Schedule a coroutine and track its task."""
        task = create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def shutdown(self) -> None:
        """Cancel and await all tracked tasks."""
        # Cancel all background tasks
        for task in self._tasks:
            task.cancel()
        # Wait for cancellation
        await asyncio.gather(*self._tasks, return_exceptions=True)

# Usage
manager = BackgroundTaskManager()
manager.create_task(background_job())
```

## Async Iteration Protocol

```python
class AsyncRange:
    """Async iterator over a range of integers."""

    start: int
    end: int
    current: int

    def __init__(self, start: int, end: int) -> None:
        """Initialize the AsyncRange instance."""
        self.start = start
        self.end = end
        self.current = start

    def __aiter__(self) -> Self:
        """Return the async iterator."""
        return self

    async def __anext__(self) -> int:
        """Return the next item, or stop the iteration."""
        if self.current >= self.end:
            raise StopAsyncIteration
        await asyncio.sleep(0.1)  # Simulate async work
        value = self.current
        self.current += 1
        return value

# Usage
async for i in AsyncRange(0, 5):
    print(i)
```

## Mixing Sync and Async

These are utility-module helpers, so they're grouped under a domain class rather than
left loose at module level — call sites read `AsyncBridge.run_in_executor(...)`, which
says where the helper comes from (see *Grouping Functions Under Classes* in `SKILL.md`).

```python
import functools

class AsyncBridge:
    """Helpers for crossing the sync/async boundary."""

    @staticmethod
    async def run_in_executor(func: Callable[..., T], *args: Any) -> T:
        """Run a blocking function in the default executor."""
        loop = asyncio.get_running_loop()

        return await loop.run_in_executor(None, func, *args)

    @staticmethod
    def run_sync(coro: Coroutine[None, None, T]) -> T:
        """Run a coroutine to completion from synchronous code."""
        loop = asyncio.new_event_loop()

        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @staticmethod
    def to_async(func: Callable[..., T]) -> Callable[..., Coroutine[None, None, T]]:
        """Wrap a sync function so it runs in an executor."""

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            """Run the wrapped function in an executor."""
            loop = asyncio.get_running_loop()

            return await loop.run_in_executor(
                None,
                functools.partial(func, *args, **kwargs),
            )

        return wrapper
```
