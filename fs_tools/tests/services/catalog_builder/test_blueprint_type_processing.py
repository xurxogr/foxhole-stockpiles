"""Tests for catalog_builder.blueprint_type_processing module."""

from typing import Any

from fs_tools.services.catalog_builder.blueprint_type_processing import process_value


class TestProcessValueBasics:
    """Tests for process_value with non-dict / no-$type inputs."""

    def test_list_processes_each_item(self) -> None:
        """A list is processed recursively, item by item."""
        data = [{"$type": "IntPropertyData", "Value": 1}, {"$type": "IntPropertyData", "Value": 2}]
        assert process_value(data) == [1, 2]

    def test_non_dict_primitive_returned_as_is(self) -> None:
        """Primitives (int, str, bool, None) pass through unchanged."""
        assert process_value(5) == 5
        assert process_value("foo") == "foo"
        assert process_value(True) is True
        assert process_value(None) is None

    def test_dict_without_type_processed_recursively(self) -> None:
        """A dict without $type has each value processed recursively."""
        data = {"a": {"$type": "IntPropertyData", "Value": 1}, "b": 2}
        assert process_value(data) == {"a": 1, "b": 2}

    def test_unknown_type_returns_value_field(self) -> None:
        """An unrecognized $type falls back to the Value field."""
        assert process_value({"$type": "SomethingUnknown", "Value": "raw"}) == "raw"

    def test_unknown_type_without_value_returns_whole_dict(self) -> None:
        """An unrecognized $type with no Value field returns the dict itself."""
        data = {"$type": "SomethingUnknown", "Other": 1}
        assert process_value(data) == data


class TestProcessPropertyData:
    """Tests for _process_property_data via process_value dispatch."""

    def test_int_property_data(self) -> None:
        """IntPropertyData variants extract the Value field."""
        assert process_value({"$type": "IntPropertyData", "Value": 42}) == 42
        assert process_value({"$type": "Int64PropertyData", "Value": 42}) == 42
        assert process_value({"$type": "UInt16PropertyData"}) == 0

    def test_bool_property_data(self) -> None:
        """BoolPropertyData extracts the Value field, defaulting to False."""
        assert process_value({"$type": "BoolPropertyData", "Value": True}) is True
        assert process_value({"$type": "BoolPropertyData"}) is False

    def test_float_property_data(self) -> None:
        """FloatPropertyData extracts the Value field, defaulting to 0.0."""
        assert process_value({"$type": "FloatPropertyData", "Value": 1.5}) == 1.5
        assert process_value({"$type": "FloatPropertyData"}) == 0.0

    def test_str_property_data_string_value(self) -> None:
        """StrPropertyData with a plain string value returns it as a string."""
        assert process_value({"$type": "StrPropertyData", "Value": "hi"}) == "hi"

    def test_str_property_data_dict_value(self) -> None:
        """StrPropertyData with a nested dict value extracts its Value field."""
        data = {"$type": "NamePropertyData", "Value": {"Value": "nested"}}
        assert process_value(data) == "nested"

    def test_str_property_data_falsy_value(self) -> None:
        """StrPropertyData with no value returns an empty string."""
        assert process_value({"$type": "StrPropertyData", "Value": None}) == ""

    def test_text_property_data_with_culture_and_guid(self) -> None:
        """TextPropertyData with both CultureInvariantString and a GUID Value returns both."""
        data = {
            "$type": "TextPropertyData",
            "CultureInvariantString": "Hello",
            "Value": "abc-guid",
        }
        assert process_value(data) == {"Text": "Hello", "Guid": "abc-guid"}

    def test_text_property_data_culture_only(self) -> None:
        """TextPropertyData with only CultureInvariantString returns just the text."""
        data = {"$type": "TextPropertyData", "CultureInvariantString": "Hello"}
        assert process_value(data) == "Hello"

    def test_text_property_data_dict_value_fallback(self) -> None:
        """TextPropertyData without CultureInvariantString falls back to Value's dict field."""
        data = {"$type": "TextPropertyData", "Value": {"CultureInvariantString": "Nested"}}
        assert process_value(data) == "Nested"

    def test_text_property_data_string_value_fallback(self) -> None:
        """TextPropertyData without CultureInvariantString falls back to str(Value)."""
        data = {"$type": "TextPropertyData", "Value": "raw-guid"}
        assert process_value(data) == "raw-guid"

    def test_text_property_data_no_text_at_all(self) -> None:
        """TextPropertyData with neither field returns an empty string."""
        assert process_value({"$type": "TextPropertyData"}) == ""

    def test_byte_and_enum_property_data(self) -> None:
        """BytePropertyData/EnumPropertyData extract Value.Value from a dict, or Value itself."""
        assert process_value({"$type": "EnumPropertyData", "Value": {"Value": "Foo"}}) == "Foo"
        assert process_value({"$type": "BytePropertyData", "Value": 3}) == 3

    def test_soft_object_property_data(self) -> None:
        """SoftObjectPropertyData extracts AssetPathName from a dict Value."""
        data = {"$type": "SoftObjectPropertyData", "Value": {"AssetPathName": "/Game/Foo"}}
        assert process_value(data) == "/Game/Foo"
        assert process_value({"$type": "SoftObjectPropertyData", "Value": "raw"}) == "raw"

    def test_object_property_data_dict_index(self) -> None:
        """ObjectPropertyData with a dict Value uses its Index field."""
        data = {"$type": "ObjectPropertyData", "Value": {"Index": 7}}
        assert process_value(data) == "Reference: 7"

    def test_object_property_data_int_index(self) -> None:
        """ObjectPropertyData with an int Value uses it directly as the index."""
        data = {"$type": "ObjectPropertyData", "Value": 9}
        assert process_value(data) == "Reference: 9"

    def test_object_property_data_other_value(self) -> None:
        """ObjectPropertyData with a non-dict, non-int Value returns it as-is."""
        assert process_value({"$type": "ObjectPropertyData", "Value": None}) is None

    def test_array_property_data(self) -> None:
        """ArrayPropertyData recursively processes each item in Value."""
        data = {
            "$type": "ArrayPropertyData",
            "Value": [{"$type": "IntPropertyData", "Value": 1}],
        }
        assert process_value(data) == [1]

    def test_array_property_data_non_list_value(self) -> None:
        """ArrayPropertyData with a non-list Value returns it unchanged."""
        assert process_value({"$type": "ArrayPropertyData", "Value": None}) is None

    def test_map_property_data(self) -> None:
        """MapPropertyData returns the Value field as-is."""
        data = {"$type": "MapPropertyData", "Value": {"a": 1}}
        assert process_value(data) == {"a": 1}

    def test_set_property_data(self) -> None:
        """SetPropertyData recursively processes each item in Value."""
        data = {"$type": "SetPropertyData", "Value": [{"$type": "IntPropertyData", "Value": 1}]}
        assert process_value(data) == [1]

    def test_set_property_data_non_list_value(self) -> None:
        """SetPropertyData with a non-list Value returns it unchanged."""
        assert process_value({"$type": "SetPropertyData", "Value": None}) is None

    def test_delegate_property_data(self) -> None:
        """Delegate/FDelegate types return the Value field as-is."""
        assert process_value({"$type": "FDelegateProperty", "Value": "cb"}) == "cb"
        assert process_value({"$type": "DelegatePropertyData", "Value": "cb"}) == "cb"

    def test_multicast_sparse_delegate_property_data(self) -> None:
        """MulticastSparseDelegatePropertyData is caught by the earlier Delegate check.

        "MulticastSparseDelegatePropertyData" contains "DelegatePropertyData" as a
        substring, so the generic Delegate branch (`data.get("Value")`, no default)
        matches first — the dedicated Multicast branch below it is unreachable.
        """
        assert process_value({"$type": "MulticastSparseDelegatePropertyData"}) is None

    def test_default_property_data_fallback(self) -> None:
        """An unrecognized *PropertyData type falls back to returning Value."""
        assert process_value({"$type": "WeirdPropertyData", "Value": "x"}) == "x"


class TestProcessStructData:
    """Tests for _process_struct_data via process_value dispatch."""

    def test_struct_property_data_processes_nested_properties(self) -> None:
        """A plain StructPropertyData merges its nested Name/Value pairs into a dict."""
        data: dict[str, Any] = {
            "$type": "StructPropertyData",
            "Value": [
                {"Name": "Foo", "$type": "IntPropertyData", "Value": 1},
                {"NoName": True},
            ],
        }
        assert process_value(data) == {"Foo": 1}

    def test_struct_property_data_non_list_value(self) -> None:
        """StructPropertyData with a non-list Value returns it unchanged."""
        assert process_value({"$type": "StructPropertyData", "Value": "raw"}) == "raw"

    def test_vector_struct_returns_value_as_is(self) -> None:
        """A Vector-flavored struct is excluded from the generic struct merge and returned as-is.

        The router only reaches _process_struct_data when $type contains both
        "PropertyData" and "Struct"; a bare "VectorPropertyData" lacks "Struct"
        and instead falls through _process_property_data's default branch.
        """
        data = {"$type": "VectorStructPropertyData", "Value": {"X": 1, "Y": 2, "Z": 3}}
        assert process_value(data) == {"X": 1, "Y": 2, "Z": 3}

    def test_guid_property_data_dict_value(self) -> None:
        """GuidPropertyData with a dict Value extracts the Guid field as a string.

        The router only reaches _process_struct_data when the $type contains both
        "PropertyData" and "Struct" (e.g. "StructGuidPropertyData"); a bare
        "GuidPropertyData" routes to _process_property_data instead and never hits
        this branch.
        """
        data = {"$type": "StructGuidPropertyData", "Value": {"Guid": "abc-123"}}
        assert process_value(data) == "abc-123"

    def test_guid_property_data_non_dict_value(self) -> None:
        """GuidPropertyData with a non-dict Value returns it unchanged."""
        data = {"$type": "StructGuidPropertyData", "Value": "already-a-string"}
        assert process_value(data) == "already-a-string"

    def test_per_platform_float_property_data(self) -> None:
        """PerPlatformFloatPropertyData extracts Value, defaulting to 0.0.

        Requires "Struct" in $type to reach _process_struct_data's dedicated
        branch — a bare "PerPlatformFloatPropertyData" would instead match the
        earlier "FloatPropertyData" substring check in _process_property_data.
        """
        data = {"$type": "StructPerPlatformFloatPropertyData", "Value": 2.5}
        assert process_value(data) == 2.5
        assert process_value({"$type": "StructPerPlatformFloatPropertyData"}) == 0.0


class TestProcessUnrealType:
    """Tests for _process_unreal_type via process_value dispatch."""

    def test_unreal_type_strips_type_key(self) -> None:
        """UnrealTypes entries are returned as a dict with the $type key removed."""
        data = {"$type": "UnrealTypes.FVector", "X": 1, "Y": 2}
        assert process_value(data) == {"X": 1, "Y": 2}


class TestProcessFieldType:
    """Tests for _process_field_type via process_value dispatch."""

    def test_field_type_returns_name_and_flags(self) -> None:
        """FieldTypes entries return a simplified Name/Flags dict."""
        data = {"$type": "FieldTypes.UBoolProperty", "Name": "bFoo", "Flags": 5, "Other": "x"}
        assert process_value(data) == {"Name": "bFoo", "Flags": 5}

    def test_field_type_defaults(self) -> None:
        """FieldTypes entries default Name/Flags when missing."""
        assert process_value({"$type": "FieldTypes.UBoolProperty"}) == {"Name": "", "Flags": 0}


class TestProcessCustomVersion:
    """Tests for _process_custom_version via process_value dispatch."""

    def test_custom_version_maps_friendly_name_to_version(self) -> None:
        """CustomVersion entries collapse to a {FriendlyName: Version} mapping."""
        data = {"$type": "CustomVersion", "FriendlyName": "Core", "Version": 3}
        assert process_value(data) == {"Core": 3}

    def test_custom_version_defaults(self) -> None:
        """CustomVersion entries default FriendlyName/Version when missing."""
        assert process_value({"$type": "CustomVersion"}) == {"Unknown": 0}
