"""Mock/real mode is per execution context and does not mutate process state."""

from concurrent.futures import ThreadPoolExecutor

from app.core.execution_mode import execution_mode, is_mock_mode


def _read_mode(value: bool) -> bool:
    with execution_mode(value):
        return is_mock_mode()


def test_parallel_modes_are_isolated():
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(_read_mode, [True, False]))
    assert values == [True, False]


def test_nested_mode_restores_outer_context():
    with execution_mode(True):
        assert is_mock_mode() is True
        with execution_mode(False):
            assert is_mock_mode() is False
        assert is_mock_mode() is True

