"""Tests for the translator module."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest
import shiboken6
from PySide6.QtCore import QObject

from foxhole_stockpiles.i18n.translator import (
    Translator,
    _deep_merge,
    _get_exe_dir,
    _get_signals,
    _load_json_file,
    get_available_languages,
    get_translator,
    off_language_changed,
    on_language_changed,
    set_language,
    t,
)


class TestTranslator:
    """Tests for the Translator class."""

    def test_init_loads_english_by_default(self) -> None:
        """Test that English translations are loaded by default."""
        translator = Translator()
        assert translator.language == "en"
        assert translator.translations != {}
        assert "language_name" in translator.translations

    def test_init_loads_specified_language(self) -> None:
        """Test that specified language is loaded."""
        translator = Translator("en")
        assert translator.language == "en"
        assert translator.translations.get("language_name") == "English"

    def test_fallback_to_english_for_unknown_language(self) -> None:
        """Test that unknown languages fall back to English."""
        translator = Translator("unknown_language_xyz")
        # Should fall back to English
        assert translator.translations.get("language_name") == "English"

    def test_get_simple_key(self) -> None:
        """Test getting a simple translation key."""
        translator = Translator("en")
        result = translator.get("language_name")
        assert result == "English"

    def test_get_nested_key(self) -> None:
        """Test getting a nested translation key."""
        translator = Translator("en")
        result = translator.get("common.close")
        assert result == "Close"

    def test_get_deeply_nested_key(self) -> None:
        """Test getting a deeply nested translation key."""
        translator = Translator("en")
        result = translator.get("main_window.menu.file")
        assert result == "&File"

    def test_get_missing_key_returns_key(self) -> None:
        """Test that missing keys return the key itself."""
        translator = Translator("en")
        result = translator.get("nonexistent.key.path")
        assert result == "nonexistent.key.path"

    def test_get_with_format_parameters(self) -> None:
        """Test getting a translation with format parameters."""
        translator = Translator("en")
        result = translator.get("main_window.title", version="1.0.0")
        assert result == "FS (Foxhole Stockpiles) - v1.0.0"

    def test_get_with_missing_format_parameter(self) -> None:
        """Test getting a translation with missing format parameters."""
        translator = Translator("en")
        # Should return the value without substitution when param is missing
        result = translator.get("main_window.title")
        assert "{version}" in result

    def test_call_is_shorthand_for_get(self) -> None:
        """Test that __call__ is a shorthand for get."""
        translator = Translator("en")
        assert translator("common.close") == translator.get("common.close")
        assert translator("main_window.title", version="2.0") == translator.get(
            "main_window.title", version="2.0"
        )


class TestGlobalTranslator:
    """Tests for global translator functions."""

    def setup_method(self) -> None:
        """Reset global translator state before each test."""
        import foxhole_stockpiles.i18n.translator as translator_module

        translator_module._translator = None
        translator_module._signals = None

    def test_get_translator_creates_default(self) -> None:
        """Test that get_translator creates a default English translator."""
        translator = get_translator()
        assert translator.language == "en"

    def test_get_translator_with_language(self) -> None:
        """Test that get_translator creates translator with specified language."""
        translator = get_translator("en")
        assert translator.language == "en"

    def test_get_translator_returns_same_instance(self) -> None:
        """Test that get_translator returns the same instance."""
        translator1 = get_translator()
        translator2 = get_translator()
        assert translator1 is translator2

    def test_get_translator_with_language_creates_new(self) -> None:
        """Test that specifying a language creates a new translator."""
        get_translator()  # Create default first
        translator2 = get_translator("en")
        # They should be different instances when language is explicitly specified
        assert translator2.language == "en"

    def test_t_function(self) -> None:
        """Test the convenience t() function."""
        result = t("common.close")
        assert result == "Close"

    def test_t_function_with_params(self) -> None:
        """Test the t() function with format parameters."""
        result = t("main_window.title", version="3.0")
        assert result == "FS (Foxhole Stockpiles) - v3.0"


class TestSetLanguage:
    """Tests for set_language function."""

    def setup_method(self) -> None:
        """Reset global translator state before each test."""
        import foxhole_stockpiles.i18n.translator as translator_module

        translator_module._translator = None
        translator_module._signals = None

    @patch("foxhole_stockpiles.i18n.translator._get_signals")
    def test_set_language_creates_new_translator(self, mock_get_signals: MagicMock) -> None:
        """Test that set_language creates a new translator."""
        mock_signals = MagicMock()
        mock_get_signals.return_value = mock_signals

        set_language("en")

        translator = get_translator()
        assert translator.language == "en"

    @patch("foxhole_stockpiles.i18n.translator._get_signals")
    def test_set_language_emits_signal(self, mock_get_signals: MagicMock) -> None:
        """Test that set_language emits language_changed signal."""
        mock_signals = MagicMock()
        mock_get_signals.return_value = mock_signals

        set_language("en")

        mock_signals.language_changed.emit.assert_called_once_with("en")


class TestGetAvailableLanguages:
    """Tests for get_available_languages function."""

    def test_returns_list_of_tuples(self) -> None:
        """Test that get_available_languages returns a list of tuples."""
        languages = get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        # Each item should be a tuple of (code, name)
        for item in languages:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_english_is_available(self) -> None:
        """Test that English is in the available languages."""
        languages = get_available_languages()
        codes = [code for code, name in languages]
        assert "en" in codes

    def test_language_names_are_strings(self) -> None:
        """Test that language names are non-empty strings."""
        languages = get_available_languages()
        for _code, name in languages:
            assert isinstance(name, str)
            assert len(name) > 0


class TestTranslationFile:
    """Tests for the translation file content."""

    def test_en_json_has_required_sections(self) -> None:
        """Test that en.json has all required sections."""
        translator = Translator("en")

        # Check required top-level keys
        assert "language_name" in translator.translations
        assert "language_code" in translator.translations
        assert "common" in translator.translations
        assert "main_window" in translator.translations
        assert "config_window" in translator.translations
        assert "server_panel" in translator.translations
        assert "gui_tab" in translator.translations

    def test_common_section_has_basic_strings(self) -> None:
        """Test that common section has basic strings."""
        translator = Translator("en")

        assert translator.get("common.save") == "Save"
        assert translator.get("common.close") == "Close"
        assert translator.get("common.browse") == "Browse..."

    def test_main_window_menu_strings(self) -> None:
        """Test that main window menu strings are present."""
        translator = Translator("en")

        assert translator.get("main_window.menu.file") == "&File"
        assert translator.get("main_window.menu.help") == "&Help"


class TestSpanishTranslations:
    """Tests for Spanish translation file."""

    def test_spanish_is_available(self) -> None:
        """Test that Spanish is in the available languages."""
        languages = get_available_languages()
        codes = [code for code, _name in languages]
        assert "es" in codes

    def test_spanish_language_name(self) -> None:
        """Test Spanish language name."""
        translator = Translator("es")
        assert translator.get("language_name") == "Español"

    def test_spanish_common_strings(self) -> None:
        """Test Spanish common strings."""
        translator = Translator("es")
        assert translator.get("common.save") == "Guardar"
        assert translator.get("common.close") == "Cerrar"

    def test_spanish_menu_strings(self) -> None:
        """Test Spanish menu strings."""
        translator = Translator("es")
        assert translator.get("main_window.menu.file") == "&Archivo"
        assert translator.get("main_window.menu.help") == "A&yuda"

    def test_spanish_format_parameters(self) -> None:
        """Test Spanish strings with format parameters."""
        translator = Translator("es")
        result = translator.get("about.version", version="2.0.0")
        assert result == "Versión 2.0.0"


class TestDeepMerge:
    """Tests for the _deep_merge function."""

    def test_simple_merge(self) -> None:
        """Test merging simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self) -> None:
        """Test merging nested dictionaries."""
        base = {"common": {"cancel": "Cancel", "save": "Save"}}
        override = {"common": {"cancel": "Abort"}}
        result = _deep_merge(base, override)
        assert result == {"common": {"cancel": "Abort", "save": "Save"}}

    def test_deeply_nested_merge(self) -> None:
        """Test merging deeply nested dictionaries."""
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"c": 10}}}
        result = _deep_merge(base, override)
        assert result == {"a": {"b": {"c": 10, "d": 2}}}

    def test_override_non_dict_with_dict(self) -> None:
        """Test overriding a non-dict value with a dict."""
        base = {"a": "string"}
        override = {"a": {"nested": "value"}}
        result = _deep_merge(base, override)
        assert result == {"a": {"nested": "value"}}


class TestLoadJsonFile:
    """Tests for the _load_json_file function."""

    def test_load_nonexistent_file(self) -> None:
        """Test loading a file that doesn't exist."""
        result = _load_json_file(Path("/nonexistent/path/file.json"))
        assert result is None

    def test_load_valid_json(self) -> None:
        """Test loading a valid JSON file."""
        with TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "test.json"
            json_file.write_text('{"key": "value"}', encoding="utf-8")
            result = _load_json_file(json_file)
            assert result == {"key": "value"}

    def test_load_invalid_json(self) -> None:
        """Test loading an invalid JSON file."""
        with TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / "test.json"
            json_file.write_text("not valid json {{{", encoding="utf-8")
            result = _load_json_file(json_file)
            assert result is None


class TestGetExeDir:
    """Tests for the _get_exe_dir function."""

    def test_returns_cwd_when_not_frozen(self) -> None:
        """Test that _get_exe_dir returns cwd when not frozen."""
        with patch("foxhole_stockpiles.i18n.translator.is_frozen", return_value=False):
            result = _get_exe_dir()
            assert result == Path.cwd()

    def test_returns_executable_parent_when_frozen(self) -> None:
        """Test that _get_exe_dir returns executable parent when frozen."""
        with patch("foxhole_stockpiles.i18n.translator.is_frozen", return_value=True):
            result = _get_exe_dir()
            assert result == Path(sys.executable).parent


class TestUserTranslations:
    """Tests for user translation merging."""

    def setup_method(self) -> None:
        """Reset global translator state before each test."""
        import foxhole_stockpiles.i18n.translator as translator_module

        translator_module._translator = None
        translator_module._signals = None

    def test_user_translations_merged(self) -> None:
        """Test that user translations are merged with bundled ones."""
        with TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "i18n" / "translations"
            user_dir.mkdir(parents=True)
            user_file = user_dir / "en.json"
            user_file.write_text('{"common": {"cancel": "USER_CANCEL"}}', encoding="utf-8")

            with patch(
                "foxhole_stockpiles.i18n.translator._get_user_translations_dir",
                return_value=user_dir,
            ):
                translator = Translator("en")
                # User override should take effect
                assert translator.get("common.cancel") == "USER_CANCEL"
                # Other keys should still work from bundled
                assert translator.get("common.save") == "Save"


class TestEdgeCases:
    """Tests for edge cases in translation."""

    def test_get_key_beyond_string_value(self) -> None:
        """Test getting a key path that goes beyond a string value."""
        translator = Translator("en")
        # language_name is a string, trying to access a child should return the key
        result = translator.get("language_name.child.grandchild")
        assert result == "language_name.child.grandchild"

    def test_format_with_wrong_parameter_name(self) -> None:
        """Test formatting with a wrong parameter name."""
        translator = Translator("en")
        # main_window.title expects {version} but we pass {wrong}
        result = translator.get("main_window.title", wrong="value")
        # Should return the unformatted string with {version} still in it
        assert "{version}" in result


class TestOffLanguageChanged:
    """Tests for off_language_changed function."""

    def setup_method(self) -> None:
        """Reset global translator state before each test."""
        import foxhole_stockpiles.i18n.translator as translator_module

        translator_module._translator = None
        translator_module._signals = None

    def test_disconnect_connected_callback(self) -> None:
        """Test disconnecting a previously connected callback."""
        callback = MagicMock()
        on_language_changed(callback)
        # Should not raise
        off_language_changed(callback)

    def test_disconnect_unconnected_callback(self) -> None:
        """Test disconnecting a callback that was never connected."""
        callback = MagicMock()
        # Should not raise even if callback was never connected
        off_language_changed(callback)

    def test_disconnect_handles_deleted_qt_object(self) -> None:
        """Test that RuntimeError is caught when Qt signals object is deleted."""
        import foxhole_stockpiles.i18n.translator as translator_module

        # Mock _get_signals to raise RuntimeError (simulates deleted Qt object)
        with patch.object(
            translator_module,
            "_get_signals",
            side_effect=RuntimeError("wrapped C/C++ object has been deleted"),
        ):
            callback = MagicMock()
            # Should not raise even when Qt object is deleted
            off_language_changed(callback)


class TestGetAvailableLanguagesEdgeCases:
    """Tests for edge cases in get_available_languages."""

    def test_handles_invalid_json_in_bundled(self) -> None:
        """Test that invalid JSON files in bundled dir are handled gracefully."""
        with TemporaryDirectory() as tmpdir:
            bundled_dir = Path(tmpdir) / "bundled"
            bundled_dir.mkdir()
            # Create a valid file
            valid_file = bundled_dir / "en.json"
            valid_file.write_text('{"language_name": "English"}', encoding="utf-8")
            # Create an invalid file
            invalid_file = bundled_dir / "broken.json"
            invalid_file.write_text("not valid json", encoding="utf-8")

            with patch(
                "foxhole_stockpiles.i18n.translator._get_bundled_translations_dir",
                return_value=bundled_dir,
            ):
                with patch(
                    "foxhole_stockpiles.i18n.translator._get_user_translations_dir",
                    return_value=Path("/nonexistent"),
                ):
                    languages = get_available_languages()
                    codes = [code for code, _ in languages]
                    assert "en" in codes
                    # broken should use filename as name
                    assert "broken" in codes

    def test_user_translations_in_available_languages(self) -> None:
        """Test that user translations appear in available languages."""
        with TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "user"
            user_dir.mkdir()
            custom_file = user_dir / "custom.json"
            custom_file.write_text('{"language_name": "Custom Lang"}', encoding="utf-8")

            with patch(
                "foxhole_stockpiles.i18n.translator._get_user_translations_dir",
                return_value=user_dir,
            ):
                languages = get_available_languages()
                codes = [code for code, _ in languages]
                names = [name for _, name in languages]
                assert "custom" in codes
                assert "Custom Lang" in names

    def test_user_invalid_json_not_in_bundled(self) -> None:
        """Test handling invalid user JSON when lang not in bundled."""
        with TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "user"
            user_dir.mkdir()
            invalid_file = user_dir / "newlang.json"
            invalid_file.write_text("invalid json", encoding="utf-8")

            with patch(
                "foxhole_stockpiles.i18n.translator._get_user_translations_dir",
                return_value=user_dir,
            ):
                languages = get_available_languages()
                codes = [code for code, _ in languages]
                # newlang should be added with code as name
                assert "newlang" in codes

    def test_empty_directories_returns_fallback(self) -> None:
        """Test that empty directories return English fallback."""
        with TemporaryDirectory() as tmpdir:
            empty_bundled = Path(tmpdir) / "bundled"
            empty_bundled.mkdir()
            empty_user = Path(tmpdir) / "user"

            with patch(
                "foxhole_stockpiles.i18n.translator._get_bundled_translations_dir",
                return_value=empty_bundled,
            ):
                with patch(
                    "foxhole_stockpiles.i18n.translator._get_user_translations_dir",
                    return_value=empty_user,
                ):
                    languages = get_available_languages()
                    assert languages == [("en", "English")]


class TestTranslatorEnglishNotFound:
    """Tests for when English translation file is not found."""

    def test_english_not_found_returns_empty(self) -> None:
        """Test that missing English file results in empty translations."""
        with TemporaryDirectory() as tmpdir:
            empty_dir = Path(tmpdir) / "translations"
            empty_dir.mkdir()

            with patch(
                "foxhole_stockpiles.i18n.translator._get_bundled_translations_dir",
                return_value=empty_dir,
            ):
                with patch(
                    "foxhole_stockpiles.i18n.translator._get_user_translations_dir",
                    return_value=Path("/nonexistent"),
                ):
                    translator = Translator("en")
                    assert translator.translations == {}


class TestBrokenTranslationStrings:
    """A translation file with bad placeholders must not break the caller."""

    @pytest.mark.parametrize(
        "text",
        ["unbalanced { brace", "positional {} field", "index {0} field", "attr {error.nope}"],
    )
    def test_returns_the_unformatted_text(self, text: str) -> None:
        """A string that cannot be formatted is returned as written.

        Args:
            text (str): The broken translation.
        """
        translator = Translator("en")
        translator.translations = {"broken": text}

        assert translator.get("broken", error="boom") == text

    def test_braces_in_a_value_are_not_expanded(self) -> None:
        """A value containing braces is inserted literally."""
        translator = Translator("en")
        translator.translations = {"message": "Failed: {error}"}

        assert translator.get("message", error="bad {path}") == "Failed: bad {path}"


class TestLanguageCallbackLifetime:
    """Subscriptions end with the QObject that owns the callback."""

    @pytest.mark.parametrize("dropped_by", ["delete", "parent"])
    def test_destroyed_owner_is_no_longer_called(self, dropped_by: str) -> None:
        """A bound method of a destroyed QObject stops receiving language changes.

        Args:
            dropped_by (str): How the owner is destroyed.
        """
        calls: list[str] = []

        class Owner(QObject):
            """Records the language changes it receives."""

            def on_change(self, language: str) -> None:
                """Record a language change.

                Args:
                    language (str): The new language.
                """
                calls.append(language)

        parent = QObject()
        owner = Owner(parent)
        on_language_changed(owner.on_change)
        _get_signals().language_changed.emit("first")

        shiboken6.delete(owner if dropped_by == "delete" else parent)
        _get_signals().language_changed.emit("second")

        assert calls == ["first"]

    def test_plain_function_stays_until_disconnected(self) -> None:
        """A callable without a QObject owner needs an explicit disconnect."""
        calls: list[str] = []

        def on_change(language: str) -> None:
            calls.append(language)

        on_language_changed(on_change)
        _get_signals().language_changed.emit("first")
        off_language_changed(on_change)
        _get_signals().language_changed.emit("second")

        assert calls == ["first"]
