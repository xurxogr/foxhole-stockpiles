"""Tests for catalog_builder.blueprint_import_resolution module."""

from fs_tools.services.catalog_builder.blueprint_import_resolution import (
    process_import,
    resolve_import_asset_path,
    resolve_import_full_path,
)


class TestResolveImportFullPath:
    """Tests for resolve_import_full_path."""

    def test_non_blueprint_class_returns_none(self) -> None:
        """Only BlueprintGeneratedClass imports are resolved."""
        import_obj = {"ClassName": "Texture2D", "OuterIndex": -1}
        assert resolve_import_full_path(import_obj=import_obj, all_imports=[]) is None

    def test_resolves_game_package_path(self) -> None:
        """A negative OuterIndex resolves to the package import's ObjectName."""
        all_imports = [{"ObjectName": "/Game/Blueprints/Items/BPFoo"}]
        import_obj = {"ClassName": "BlueprintGeneratedClass", "OuterIndex": -1}
        assert resolve_import_full_path(import_obj=import_obj, all_imports=all_imports) == (
            "/Game/Blueprints/Items/BPFoo"
        )

    def test_non_game_package_path_returns_none(self) -> None:
        """A resolved package path outside /Game/ returns None."""
        all_imports = [{"ObjectName": "/Script/CoreUObject"}]
        import_obj = {"ClassName": "BlueprintGeneratedClass", "OuterIndex": -1}
        assert resolve_import_full_path(import_obj=import_obj, all_imports=all_imports) is None

    def test_non_negative_outer_index_returns_none(self) -> None:
        """A non-negative OuterIndex is never followed, so the result is None."""
        import_obj = {"ClassName": "BlueprintGeneratedClass", "OuterIndex": 0}
        assert resolve_import_full_path(import_obj=import_obj, all_imports=[]) is None

    def test_out_of_range_outer_index_returns_none(self) -> None:
        """An OuterIndex pointing outside all_imports is caught and returns None."""
        import_obj = {"ClassName": "BlueprintGeneratedClass", "OuterIndex": -5}
        assert resolve_import_full_path(import_obj=import_obj, all_imports=[]) is None


class TestResolveImportAssetPath:
    """Tests for resolve_import_asset_path."""

    def test_engine_class_names_are_skipped(self) -> None:
        """Package/Class/Function/ScriptStruct imports are never assets."""
        for class_name in ("Package", "Class", "Function", "ScriptStruct"):
            import_obj = {"ClassName": class_name, "OuterIndex": -1}
            assert resolve_import_asset_path(import_obj=import_obj, all_imports=[]) is None

    def test_resolves_and_normalizes_asset_path(self) -> None:
        """A resolved /Game/ path is normalized before being returned."""
        all_imports = [{"ObjectName": "/Game/Textures/UI/Icon"}]
        import_obj = {"ClassName": "Texture2D", "OuterIndex": -1}
        result = resolve_import_asset_path(import_obj=import_obj, all_imports=all_imports)
        assert result is not None

    def test_non_negative_outer_index_returns_none(self) -> None:
        """A non-negative OuterIndex is never followed, so the result is None."""
        import_obj = {"ClassName": "Texture2D", "OuterIndex": 0}
        assert resolve_import_asset_path(import_obj=import_obj, all_imports=[]) is None

    def test_non_game_package_path_returns_none(self) -> None:
        """A resolved package path outside /Game/ returns None."""
        all_imports = [{"ObjectName": "/Script/Engine"}]
        import_obj = {"ClassName": "Texture2D", "OuterIndex": -1}
        assert resolve_import_asset_path(import_obj=import_obj, all_imports=all_imports) is None

    def test_out_of_range_outer_index_returns_none(self) -> None:
        """An OuterIndex pointing outside all_imports is caught and returns None."""
        import_obj = {"ClassName": "Texture2D", "OuterIndex": -5}
        assert resolve_import_asset_path(import_obj=import_obj, all_imports=[]) is None


class TestProcessImport:
    """Tests for process_import."""

    def test_delegates_to_resolve_import_full_path(self) -> None:
        """process_import returns the full path for BlueprintGeneratedClass imports."""
        all_imports = [{"ObjectName": "/Game/Blueprints/Items/BPFoo"}]
        data = {"ClassName": "BlueprintGeneratedClass", "OuterIndex": -1}
        assert process_import(data=data, all_imports=all_imports) == "/Game/Blueprints/Items/BPFoo"

    def test_non_blueprint_returns_none(self) -> None:
        """process_import returns None for non-blueprint imports."""
        data = {"ClassName": "Texture2D", "OuterIndex": -1}
        assert process_import(data=data, all_imports=[]) is None
