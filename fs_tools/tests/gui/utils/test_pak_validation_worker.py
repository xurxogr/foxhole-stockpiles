"""Tests for PakValidationWorker."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

from fs_tools.gui.utils.pak_validation_worker import PakValidationWorker
from fs_tools.models.pak_validation_result import PakValidationResult


def test_pak_validation_worker_initialization(tmp_path: Path) -> None:
    """Test PakValidationWorker initialization.

    Args:
        tmp_path: Temporary directory path
    """
    pak_files = ["test1.pak", "test2.pak"]
    extractor_tool = tmp_path / "repak.exe"

    worker = PakValidationWorker(
        pak_files=pak_files,
        extractor_tool=extractor_tool,
    )

    assert worker.pak_files == pak_files
    assert worker.extractor_tool == extractor_tool


def test_pak_validation_worker_run_success(qtbot: Any, tmp_path: Path) -> None:
    """Test PakValidationWorker run method on success.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    pak_files = ["test.pak"]
    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.touch()

    worker = PakValidationWorker(
        pak_files=pak_files,
        extractor_tool=extractor_tool,
    )

    # Create expected result
    expected_result = PakValidationResult()
    expected_result.is_valid = True
    expected_result.has_crate_icon = True
    expected_result.has_subicons = True
    expected_result.subicons_count = 5

    # Mock the validation function
    async def mock_validate(*args: Any, **kwargs: Any) -> PakValidationResult:
        return expected_result

    try:
        with patch(
            "fs_tools.gui.utils.pak_validation_worker.PakExtractor.validate_required_assets",
            side_effect=mock_validate,
        ):
            with qtbot.waitSignal(worker.validation_complete, timeout=5000) as blocker:
                worker.start()

        result = blocker.args[0]
        assert result.is_valid is True
        assert result.has_crate_icon is True
        assert result.has_subicons is True
    finally:
        # Ensure worker is properly cleaned up
        if worker.isRunning():
            worker.wait(1000)


def test_pak_validation_worker_run_failure(qtbot: Any, tmp_path: Path) -> None:
    """Test PakValidationWorker run method on validation failure.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    pak_files = ["test.pak"]
    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.touch()

    worker = PakValidationWorker(
        pak_files=pak_files,
        extractor_tool=extractor_tool,
    )

    # Create expected result
    expected_result = PakValidationResult()
    expected_result.is_valid = False
    expected_result.has_crate_icon = False
    expected_result.has_subicons = False
    expected_result.error_message = "Missing required assets"

    # Mock the validation function
    async def mock_validate(*args: Any, **kwargs: Any) -> PakValidationResult:
        return expected_result

    try:
        with patch(
            "fs_tools.gui.utils.pak_validation_worker.PakExtractor.validate_required_assets",
            side_effect=mock_validate,
        ):
            with qtbot.waitSignal(worker.validation_complete, timeout=5000) as blocker:
                worker.start()

        result = blocker.args[0]
        assert result.is_valid is False
        assert result.error_message == "Missing required assets"
    finally:
        # Ensure worker is properly cleaned up
        if worker.isRunning():
            worker.wait(1000)


def test_pak_validation_worker_run_exception(qtbot: Any, tmp_path: Path) -> None:
    """Test PakValidationWorker run method handles exceptions.

    Args:
        qtbot: PyQt test fixture
        tmp_path: Temporary directory path
    """
    pak_files = ["test.pak"]
    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.touch()

    worker = PakValidationWorker(
        pak_files=pak_files,
        extractor_tool=extractor_tool,
    )

    # Mock the validation function to raise an exception
    async def mock_validate(*args: Any, **kwargs: Any) -> PakValidationResult:
        raise RuntimeError("Test error")

    with patch(
        "fs_tools.gui.utils.pak_validation_worker.PakExtractor.validate_required_assets",
        side_effect=mock_validate,
    ):
        with qtbot.waitSignal(worker.validation_complete, timeout=5000) as blocker:
            worker.start()

    result = blocker.args[0]
    assert result.is_valid is False
    assert "Test error" in result.error_message


# Direct run() tests for coverage (coverage doesn't track QThread.start() properly)
class TestPakValidationWorkerRunDirect:
    """Tests that call run() directly for coverage tracking."""

    def test_run_success_direct(self, tmp_path: Path) -> None:
        """Test run() method directly for successful validation."""
        pak_files = ["test.pak"]
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        worker = PakValidationWorker(
            pak_files=pak_files,
            extractor_tool=extractor_tool,
        )

        expected_result = PakValidationResult()
        expected_result.is_valid = True
        expected_result.has_crate_icon = True

        async def mock_validate(*args: Any, **kwargs: Any) -> PakValidationResult:
            return expected_result

        emitted_results: list[PakValidationResult] = []
        worker.validation_complete.connect(lambda r: emitted_results.append(r))

        with patch(
            "fs_tools.gui.utils.pak_validation_worker.PakExtractor.validate_required_assets",
            side_effect=mock_validate,
        ):
            # Call run() directly instead of start() for coverage
            worker.run()

        assert len(emitted_results) == 1
        assert emitted_results[0].is_valid is True

    def test_run_exception_direct(self, tmp_path: Path) -> None:
        """Test run() method directly handles exceptions."""
        pak_files = ["test.pak"]
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        worker = PakValidationWorker(
            pak_files=pak_files,
            extractor_tool=extractor_tool,
        )

        async def mock_validate(*args: Any, **kwargs: Any) -> PakValidationResult:
            raise RuntimeError("Validation failed")

        emitted_results: list[PakValidationResult] = []
        worker.validation_complete.connect(lambda r: emitted_results.append(r))

        with patch(
            "fs_tools.gui.utils.pak_validation_worker.PakExtractor.validate_required_assets",
            side_effect=mock_validate,
        ):
            # Call run() directly for coverage
            worker.run()

        assert len(emitted_results) == 1
        assert emitted_results[0].is_valid is False
        assert "Validation failed" in emitted_results[0].error_message
