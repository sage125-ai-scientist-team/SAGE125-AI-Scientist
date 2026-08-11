"""Wave B per-question isolation and retry-compatibility tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from app.batch.errors import BatchRunnerError
from app.contracts.batch import BatchJob, CheckpointRecord, ResumePolicy


def _api():
    import app.batch.isolation as isolation

    return isolation


def _input_hash(question_id: str) -> str:
    return hashlib.sha256(f"synthetic:{question_id}".encode()).hexdigest()


def _job(
    question_id: str,
    *,
    source_hash: str = "a" * 64,
    input_hash: str | None = None,
) -> BatchJob:
    normalized_input_hash = input_hash or _input_hash(question_id)
    prefix = normalized_input_hash[:16]
    return BatchJob(
        batch_id="wave-b-synthetic",
        question_id=question_id,
        source_hash=source_hash,
        input_hash=normalized_input_hash,
        workspace=f"wave-b-synthetic/{question_id}/workspace",
        context_id=f"ctx:wave-b-synthetic:{question_id}:{prefix}",
        cache_namespace=f"cache:wave-b-synthetic:{question_id}:{prefix}",
    )


def _identity(question_id: str):
    return _api().build_isolation_identity(_job(question_id))


def test_125_questions_have_unique_wave_a_compatible_isolation_ids() -> None:
    jobs = [_job(f"Q{number:03d}") for number in range(1, 126)]
    identities = [_api().build_isolation_identity(job) for job in jobs]

    for job, identity in zip(jobs, identities, strict=True):
        assert identity.workspace == job.workspace
        assert identity.context_id == job.context_id
        assert identity.cache_namespace == job.cache_namespace
        assert identity.source_hash == job.source_hash
        assert identity.input_hash == job.input_hash
    for field_name in (
        "workspace",
        "context_id",
        "memory_namespace",
        "cache_namespace",
        "prompt_namespace",
    ):
        assert len({getattr(value, field_name) for value in identities}) == 125


def test_distinct_questions_do_not_share_context_objects() -> None:
    api = _api()
    contexts = [
        api.create_isolated_context(_identity("Q001")),
        api.create_isolated_context(_identity("Q002")),
    ]

    api.validate_isolation_boundary(contexts)

    assert contexts[0] is not contexts[1]
    assert contexts[0].identity.context_id != contexts[1].identity.context_id


def test_distinct_questions_do_not_share_memory() -> None:
    api = _api()
    left = api.create_isolated_context(_identity("Q001"))
    right = api.create_isolated_context(_identity("Q002"))

    assert left.memory is not right.memory
    assert left.identity.memory_namespace != right.identity.memory_namespace


def test_distinct_questions_do_not_share_cache() -> None:
    api = _api()
    left = api.create_isolated_context(_identity("Q001"))
    right = api.create_isolated_context(_identity("Q002"))

    assert left.cache is not right.cache
    assert left.identity.cache_namespace != right.identity.cache_namespace


def test_distinct_questions_do_not_share_prompt_namespace() -> None:
    api = _api()
    left = api.create_isolated_context(_identity("Q001"))
    right = api.create_isolated_context(_identity("Q002"))

    assert left.prompt_context is not right.prompt_context
    assert left.identity.prompt_namespace != right.identity.prompt_namespace


def test_previous_result_cross_question_reuse_is_rejected() -> None:
    api = _api()
    result = api.QuestionScopedResult(
        question_id="Q001",
        source_hash="a" * 64,
        input_hash=_input_hash("Q001"),
        payload={"synthetic": True},
    )

    with pytest.raises(BatchRunnerError) as raised:
        api.create_isolated_context(_identity("Q002"), previous_result=result)

    assert raised.value.error_code == "PREVIOUS_RESULT_QUESTION_MISMATCH"


def test_retry_accepts_same_question_compatible_wave_a_checkpoint() -> None:
    api = _api()
    job = _job("Q001")

    restored = api.validate_retry_scope(
        api.build_isolation_identity(job),
        CheckpointRecord.from_job(job),
        job,
        ResumePolicy(),
    )

    assert restored == job
    assert restored is not job


def test_retry_rejects_checkpoint_from_another_question() -> None:
    api = _api()
    expected = _job("Q002")

    with pytest.raises(BatchRunnerError) as raised:
        api.validate_retry_scope(
            api.build_isolation_identity(expected),
            CheckpointRecord.from_job(_job("Q001")),
            expected,
            ResumePolicy(),
        )

    assert raised.value.error_code == "CHECKPOINT_QUESTION_MISMATCH"


def test_retry_rejects_input_hash_mismatch() -> None:
    api = _api()
    checkpoint_job = _job("Q001")
    expected = _job("Q001", input_hash="f" * 64)

    with pytest.raises(BatchRunnerError) as raised:
        api.validate_retry_scope(
            api.build_isolation_identity(expected),
            CheckpointRecord.from_job(checkpoint_job),
            expected,
            ResumePolicy(),
        )

    assert raised.value.error_code == "STALE_CHECKPOINT_INPUT_HASH"


def test_retry_rejects_source_hash_mismatch() -> None:
    api = _api()
    checkpoint_job = _job("Q001", source_hash="a" * 64)
    expected = _job("Q001", source_hash="f" * 64)

    with pytest.raises(BatchRunnerError) as raised:
        api.validate_retry_scope(
            api.build_isolation_identity(expected),
            CheckpointRecord.from_job(checkpoint_job),
            expected,
            ResumePolicy(),
        )

    assert raised.value.error_code == "STALE_CHECKPOINT_SOURCE_HASH"


def test_forged_namespace_collision_fails_closed() -> None:
    api = _api()
    left = api.create_isolated_context(_identity("Q001"))
    forged = replace(
        _identity("Q002"),
        cache_namespace=left.identity.cache_namespace,
    )

    with pytest.raises(BatchRunnerError) as raised:
        api.create_isolated_context(forged)

    assert raised.value.error_code == "ISOLATION_IDENTITY_INVALID"


def test_shared_mutable_state_alias_fails_closed() -> None:
    api = _api()
    left = api.create_isolated_context(_identity("Q001"))
    right = api.create_isolated_context(_identity("Q002"))
    right.memory = left.memory

    with pytest.raises(BatchRunnerError) as raised:
        api.validate_isolation_boundary([left, right])

    assert raised.value.error_code == "MUTABLE_STATE_ALIAS"


def test_reset_clears_mutable_state_and_preserves_identity() -> None:
    api = _api()
    identity = _identity("Q001")
    context = api.create_isolated_context(
        identity,
        prompt_context={"synthetic": "prompt"},
        previous_result=api.QuestionScopedResult(
            question_id="Q001",
            source_hash=identity.source_hash,
            input_hash=identity.input_hash,
            payload={"synthetic": True},
        ),
    )
    context.memory["value"] = 1
    context.cache["value"] = 2

    api.reset_mutable_question_state(context)

    assert context.identity == identity
    assert context.memory == {}
    assert context.cache == {}
    assert context.prompt_context == {}
    assert context.previous_result is None
