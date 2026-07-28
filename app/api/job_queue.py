"""有界进程内 Job 队列与上游 pipeline adapter。"""

from __future__ import annotations

import queue
import re
import threading
import time
from pathlib import Path
from typing import Callable, Protocol

from app.api.contracts import JobStatus
from app.api.job_store import InvalidTransition, JobRecord, JobStore
from app.core.logging import get_logger, mask_text


logger = get_logger("api.jobs")


class QueueCapacityError(RuntimeError):
    pass


class JobRunner(Protocol):
    def run(self, job: JobRecord, progress_callback: Callable[[dict], None]) -> str: ...


class JobQueue(Protocol):
    def start(self) -> None: ...
    def submit(self, job_id: str) -> None: ...
    def stop(self, timeout: float = 2.0) -> None: ...


class PipelineJobRunner:
    """仅通过现有公开 pipeline 入口执行，不复制上游业务逻辑。"""

    def run(self, job: JobRecord, progress_callback: Callable[[dict], None]) -> str:
        from app.core.run_progress import progress_reporting
        from app.workflow.pipeline import run_pipeline_with_state

        request = job.request_payload
        options = request.get("options") or {}
        with progress_reporting(progress_callback):
            _, state = run_pipeline_with_state(
                question_id=request["question_id"],
                use_local_rag=bool(options.get("use_local_rag", True)),
                use_deep_research=bool(options.get("use_deep_research", True)),
                use_open_literature=bool(options.get("use_open_literature", True)),
                reviewer_auto_revision=bool(
                    options.get("reviewer_auto_revision", True)
                ),
                mock_mode=request.get("mode", "mock") == "mock",
            )
        return str(state.run_id)


def _safe_error(exc: Exception) -> str:
    message = mask_text(str(exc))
    project = str(Path.cwd())
    if project:
        message = message.replace(project, "<project>")
    message = re.sub(r"(?<!:)(?:/[^\s,:;]+){2,}", "<path>", message)
    message = re.sub(r"[A-Za-z]:\\(?:[^\\\s]+\\){1,}[^\\\s]*", "<path>", message)
    return message[:500] or type(exc).__name__


def _classify_error(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, FileNotFoundError):
        return "QUESTION_SOURCE_MISSING", False
    if isinstance(exc, ValueError):
        return "INVALID_JOB_INPUT", False
    if isinstance(exc, TimeoutError):
        return "UPSTREAM_TIMEOUT", True
    if isinstance(exc, ConnectionError):
        return "UPSTREAM_CONNECTION_ERROR", True
    return "JOB_EXECUTION_FAILED", False


class InProcessJobQueue:
    def __init__(
        self,
        store: JobStore,
        runner: JobRunner,
        *,
        capacity: int = 100,
        worker_count: int = 1,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity 必须大于 0")
        if worker_count < 1:
            raise ValueError("worker_count 必须大于 0")
        self.store = store
        self.runner = runner
        self.capacity = capacity
        self.worker_count = worker_count
        self._queue: queue.Queue[str | object] = queue.Queue(maxsize=capacity)
        self._stop_token = object()
        self._threads: list[threading.Thread] = []
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        for index in range(self.worker_count):
            thread = threading.Thread(
                target=self._worker,
                name=f"sage125-job-worker-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

        for job_id in self.store.recover_interrupted_jobs():
            try:
                self.submit(job_id)
            except QueueCapacityError:
                logger.warning(
                    "恢复队列已满，任务保留 queued：job_id=%s", job_id
                )

    def submit(self, job_id: str) -> None:
        if not self._started:
            raise RuntimeError("JobQueue 尚未启动")
        try:
            self._queue.put_nowait(job_id)
        except queue.Full as exc:
            raise QueueCapacityError("任务队列已满。") from exc

    def stop(self, timeout: float = 2.0) -> None:
        if not self._started:
            return
        deadline = time.monotonic() + timeout
        for _ in self._threads:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    self._queue.put(self._stop_token, timeout=min(0.1, remaining))
                    break
                except queue.Full:
                    continue
        for thread in self._threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        self._threads.clear()
        self._started = False

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._stop_token:
                    return
                self._execute(str(item))
            finally:
                self._queue.task_done()

    def _execute(self, job_id: str) -> None:
        try:
            job = self.store.begin_attempt(job_id)
        except InvalidTransition:
            return
        logger.info(
            "job_started job_id=%s correlation_id=%s question_id=%s attempt=%d",
            job.job_id,
            job.correlation_id,
            job.question_id,
            job.attempt,
        )

        def progress(payload: dict) -> None:
            stage = str(payload.get("stage") or "running")
            self.store.update_progress(job_id, stage)

        try:
            upstream_run_id = self.runner.run(job, progress)
            self.store.transition(
                job_id,
                JobStatus.COMPLETED,
                stage="completed",
                actor="worker",
                source="queue",
                upstream_run_id=upstream_run_id,
            )
            logger.info(
                "job_completed job_id=%s correlation_id=%s upstream_run_id=%s",
                job.job_id,
                job.correlation_id,
                upstream_run_id,
            )
        except Exception as exc:  # noqa: BLE001
            current = self.store.get_job(job_id)
            error_code, retryable = _classify_error(exc)
            if retryable and current.attempt < current.max_attempts:
                self.store.transition(
                    job_id,
                    JobStatus.RETRYING,
                    actor="worker",
                    source="queue",
                    error_code=error_code,
                    error_message=_safe_error(exc),
                    retryable=True,
                )
                self.store.transition(
                    job_id,
                    JobStatus.QUEUED,
                    actor="worker",
                    source="queue",
                )
                try:
                    self.submit(job_id)
                    return
                except QueueCapacityError:
                    pass
            self.store.transition(
                job_id,
                JobStatus.FAILED,
                stage="failed",
                actor="worker",
                source="queue",
                error_code=error_code,
                error_message=_safe_error(exc),
                retryable=retryable,
            )
            logger.warning(
                "job_failed job_id=%s correlation_id=%s code=%s retryable=%s",
                job.job_id,
                job.correlation_id,
                error_code,
                retryable,
            )
