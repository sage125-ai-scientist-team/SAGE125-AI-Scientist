"""有界进程内 Job 队列与上游 pipeline adapter。"""

from __future__ import annotations

import queue
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from app.api.contracts import JobStatus
from app.api.job_store import InvalidTransition, JobRecord, JobStore
from app.core.logging import get_logger, mask_text


logger = get_logger("api.jobs")


class QueueCapacityError(RuntimeError):
    pass


class JobDeadlineExceeded(TimeoutError):
    """Raised cooperatively when a persisted job deadline has elapsed."""


@dataclass(frozen=True)
class CompletionEvidence:
    """T08 写入外部 completed 前必须具备的最小证明。"""

    required_artifacts_present: bool = False
    quality_gate_passed: bool = False
    blocking_issues_closed: bool = False
    truth_status_explicit: bool = False
    traceable_and_serializable: bool = False

    @property
    def allows_completion(self) -> bool:
        return all(
            (
                self.required_artifacts_present,
                self.quality_gate_passed,
                self.blocking_issues_closed,
                self.truth_status_explicit,
                self.traceable_and_serializable,
            )
        )

    @property
    def missing_requirements(self) -> tuple[str, ...]:
        checks = {
            "required_artifacts_present": self.required_artifacts_present,
            "quality_gate_passed": self.quality_gate_passed,
            "blocking_issues_closed": self.blocking_issues_closed,
            "truth_status_explicit": self.truth_status_explicit,
            "traceable_and_serializable": self.traceable_and_serializable,
        }
        return tuple(name for name, passed in checks.items() if not passed)


@dataclass(frozen=True)
class JobRunResult:
    upstream_run_id: str
    completion_evidence: CompletionEvidence | None = None

    @property
    def completion_verified(self) -> bool:
        return bool(
            self.completion_evidence
            and self.completion_evidence.allows_completion
        )


def _normalize_run_result(result: JobRunResult | str) -> JobRunResult:
    """兼容旧 runner 的裸 run_id，但绝不把它视为完成证明。"""
    if isinstance(result, JobRunResult):
        return result
    if isinstance(result, str) and result.strip():
        return JobRunResult(upstream_run_id=result.strip())
    raise TypeError("JobRunner 必须返回 JobRunResult 或非空 upstream_run_id。")


class JobRunner(Protocol):
    def run(
        self,
        job: JobRecord,
        progress_callback: Callable[[dict], None],
    ) -> JobRunResult | str: ...


class JobQueue(Protocol):
    def start(self) -> None: ...
    def submit(self, job_id: str) -> None: ...
    def stop(self, timeout: float = 2.0) -> None: ...


class PipelineJobRunner:
    """调用现有 pipeline；完成资格等待 Wave B 的 owner 契约适配。"""

    def run(
        self,
        job: JobRecord,
        progress_callback: Callable[[dict], None],
    ) -> JobRunResult:
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
        # 当前仓库已有 T02/T03/T05 公开契约，但 Wave A runner 尚未完成适配。
        # 只保留上游引用；不得从内部对象或文件存在性推断外部 completed。
        return JobRunResult(upstream_run_id=str(state.run_id))


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


def _deadline_exceeded(job: JobRecord) -> bool:
    if not job.deadline_at:
        return False
    deadline = datetime.fromisoformat(job.deadline_at)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= deadline.astimezone(timezone.utc)


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
        self._recovery_backlog: deque[str] = deque()
        self._recovery_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._threads: list[threading.Thread] = []
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._stop_requested.clear()
        self._started = True
        for index in range(self.worker_count):
            thread = threading.Thread(
                target=self._worker,
                name=f"sage125-job-worker-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

        with self._recovery_lock:
            self._recovery_backlog.extend(
                self.store.recover_interrupted_jobs()
            )
        self._pump_recovery_backlog()

    def _pump_recovery_backlog(self) -> None:
        if self._stop_requested.is_set():
            return
        with self._recovery_lock:
            while self._recovery_backlog:
                try:
                    self._queue.put_nowait(self._recovery_backlog[0])
                except queue.Full:
                    return
                self._recovery_backlog.popleft()

    def submit(self, job_id: str) -> None:
        if not self._started:
            raise RuntimeError("JobQueue 尚未启动")
        if self._stop_requested.is_set():
            raise RuntimeError("JobQueue 正在停止")
        try:
            self._queue.put_nowait(job_id)
        except queue.Full as exc:
            raise QueueCapacityError("任务队列已满。") from exc

    def stop(self, timeout: float = 2.0) -> None:
        if not self._started:
            return
        self._stop_requested.set()
        deadline = time.monotonic() + timeout
        for thread in self._threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        alive = [thread for thread in self._threads if thread.is_alive()]
        if alive:
            logger.warning(
                "job_queue_stop_timed_out alive_workers=%d queued=%d recovery_backlog=%d",
                len(alive),
                self._queue.qsize(),
                len(self._recovery_backlog),
            )
            self._threads = alive
            return
        self._threads.clear()
        self._queue = queue.Queue(maxsize=self.capacity)
        with self._recovery_lock:
            self._recovery_backlog.clear()
        self._started = False

    def _worker(self) -> None:
        while not self._stop_requested.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._execute(str(item))
            finally:
                self._queue.task_done()
                self._pump_recovery_backlog()

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
            if _deadline_exceeded(job):
                raise JobDeadlineExceeded("job execution deadline exceeded")
            stage = str(payload.get("stage") or "running")
            self.store.update_progress(job_id, stage)

        try:
            result = _normalize_run_result(self.runner.run(job, progress))
            if _deadline_exceeded(job):
                raise JobDeadlineExceeded("job execution deadline exceeded")
            if result.completion_verified:
                self.store.transition(
                    job_id,
                    JobStatus.COMPLETED,
                    stage="completed",
                    actor="worker",
                    source="queue",
                    upstream_run_id=result.upstream_run_id,
                )
                logger.info(
                    "job_completed job_id=%s correlation_id=%s upstream_run_id=%s",
                    job.job_id,
                    job.correlation_id,
                    result.upstream_run_id,
                )
            else:
                evidence = result.completion_evidence or CompletionEvidence()
                self.store.transition(
                    job_id,
                    JobStatus.WAITING_FEEDBACK,
                    stage="awaiting_completion_verification",
                    actor="worker",
                    source="completion_guard",
                    upstream_run_id=result.upstream_run_id,
                )
                logger.info(
                    "job_completion_deferred job_id=%s correlation_id=%s "
                    "upstream_run_id=%s missing=%s",
                    job.job_id,
                    job.correlation_id,
                    result.upstream_run_id,
                    ",".join(evidence.missing_requirements),
                )
        except JobDeadlineExceeded:
            self.store.transition(
                job_id,
                JobStatus.TIMED_OUT,
                stage="timed_out",
                actor="worker",
                source="deadline",
                error_code="JOB_TIMEOUT",
                error_message="任务超过执行时限。",
                retryable=False,
            )
            logger.warning(
                "job_timed_out job_id=%s correlation_id=%s",
                job.job_id,
                job.correlation_id,
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
                if self._stop_requested.is_set():
                    logger.info(
                        "job_retry_deferred_for_restart job_id=%s correlation_id=%s",
                        job.job_id,
                        job.correlation_id,
                    )
                    return
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
