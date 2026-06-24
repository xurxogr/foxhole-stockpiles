"""Foxhole world region (hex) enum."""

from __future__ import annotations

from enum import StrEnum


class Hex(StrEnum):
    """Foxhole world regions.

    Values are the in-game hex codes used in save files and the
    clipboard export. Use :meth:`from_display` to resolve the localized
    region name from a clipboard export to its code.
    """

    ACRITHIA = "AcrithiaHex"
    ALLODS_BIGHT = "AllodsBightHex"
    ASH_FIELDS = "AshFieldsHex"
    BASIN_SIONNACH = "BasinSionnachHex"
    CALLAHANS_PASSAGE = "CallahansPassageHex"
    CALLUMS_CAPE = "CallumsCapeHex"
    CLAHSTRA = "ClahstraHex"
    CLANSHEAD_VALLEY = "ClansheadValleyHex"
    DEAD_LANDS = "DeadLandsHex"
    DROWNED_VALE = "DrownedValeHex"
    ENDLESS_SHORE = "EndlessShoreHex"
    FARRANAC_COAST = "FarranacCoastHex"
    FISHERMANS_ROW = "FishermansRowHex"
    GODCROFTS = "GodcroftsHex"
    GREAT_MARCH = "GreatMarchHex"
    GUTTER = "GutterHex"
    HEARTLANDS = "HeartlandsHex"
    HOWL_COUNTY = "HowlCountyHex"
    KALOKAI = "KalokaiHex"
    KINGS_CAGE = "KingsCageHex"
    KUURA_STRAND = "KuuraStrandHex"
    LINN_MERCY = "LinnMercyHex"
    LOCH_MOR = "LochMorHex"
    LYKOS_ISLE = "LykosIsleHex"
    MARBAN_HOLLOW = "MarbanHollow"
    MOORING_COUNTY = "MooringCountyHex"
    MORGENS_CROSSING = "MorgensCrossingHex"
    NEVISH_LINE = "NevishLineHex"
    OARBREAKER = "OarbreakerHex"
    OLAVIS_WAKE = "OlavisWakeHex"
    ONYX = "OnyxHex"
    ORIGIN = "OriginHex"
    PALANTINE_BERM = "PalantineBermHex"
    PARI_PEAK = "PariPeakHex"
    PIPERS_ENCLAVE = "PipersEnclaveHex"
    REACHING_TRAIL = "ReachingTrailHex"
    REAVERS_PASS = "ReaversPassHex"
    RED_RIVER = "RedRiverHex"
    SABLEPORT = "SableportHex"
    SHACKLED_CHASM = "ShackledChasmHex"
    SPEAKING_WOODS = "SpeakingWoodsHex"
    STEMA_LANDING = "StemaLandingHex"
    STLICAN_SHELF = "StlicanShelfHex"
    STONECRADLE = "StonecradleHex"
    TEMPEST_ISLAND = "TempestIslandHex"
    TERMINUS = "TerminusHex"
    THE_FINGERS = "TheFingersHex"
    TYRANT_FOOTHILLS = "TyrantFoothillsHex"
    UMBRAL_WILDWOOD = "UmbralWildwoodHex"
    VIPER_PIT = "ViperPitHex"
    WEATHERED_EXPANSE = "WeatheredExpanseHex"
    WESTGATE = "WestgateHex"
    WRESTA = "WrestaHex"

    UNDEFINED = "Undefined"

    @classmethod
    def from_display(cls, display: str) -> Hex:
        """Resolve a region display name to its hex code.

        Args:
            display (str): The region name from a clipboard export header.

        Returns:
            Hex: The matching region, or :attr:`UNDEFINED` when unknown.
        """
        return _BY_DISPLAY.get(_normalize(display), cls.UNDEFINED)

    @property
    def display_name(self) -> str:
        """The human-readable region name.

        Returns:
            str: The display name, or the raw code when not mapped.
        """
        return _DISPLAY_NAMES.get(self, self.value)


# Curly apostrophe variants the in-game names use, folded to ASCII so
# clipboard text and the table below compare equal.
_APOSTROPHES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "´": "'", "`": "'"})


def _normalize(text: str) -> str:
    """Normalize a region name for case/apostrophe-insensitive matching.

    Args:
        text (str): Raw region name.

    Returns:
        str: Lower-cased, apostrophe-folded, trimmed name.
    """
    return text.translate(_APOSTROPHES).strip().lower()


_DISPLAY_NAMES: dict[Hex, str] = {
    Hex.ACRITHIA: "Acrithia",
    Hex.ALLODS_BIGHT: "Allods Bight",
    Hex.ASH_FIELDS: "Ash Fields",
    Hex.BASIN_SIONNACH: "Basin Sionnach",
    Hex.CALLAHANS_PASSAGE: "Callahan's Passage",
    Hex.CALLUMS_CAPE: "Callum's Cape",
    Hex.CLAHSTRA: "Clahstra",
    Hex.CLANSHEAD_VALLEY: "Clanshead Valley",
    Hex.DEAD_LANDS: "Deadlands",
    Hex.DROWNED_VALE: "Drowned Vale",
    Hex.ENDLESS_SHORE: "Endless Shore",
    Hex.FARRANAC_COAST: "Farranac Coast",
    Hex.FISHERMANS_ROW: "Fisherman's Row",
    Hex.GODCROFTS: "Godcrofts",
    Hex.GREAT_MARCH: "Great March",
    Hex.GUTTER: "Gutter",
    Hex.HEARTLANDS: "Heartlands",
    Hex.HOWL_COUNTY: "Howl County",
    Hex.KALOKAI: "Kalokai",
    Hex.KINGS_CAGE: "Kings Cage",
    Hex.KUURA_STRAND: "Kuura Strand",
    Hex.LINN_MERCY: "Linn of Mercy",
    Hex.LOCH_MOR: "Loch Mor",
    Hex.LYKOS_ISLE: "Lykos Isle",
    Hex.MARBAN_HOLLOW: "Marban Hollow",
    Hex.MOORING_COUNTY: "Mooring County",
    Hex.MORGENS_CROSSING: "Morgens Crossing",
    Hex.NEVISH_LINE: "Nevish Line",
    Hex.OARBREAKER: "Oarbreaker",
    Hex.OLAVIS_WAKE: "Olavi's Wake",
    Hex.ONYX: "Onyx",
    Hex.ORIGIN: "Origin",
    Hex.PALANTINE_BERM: "Palantine Berm",
    Hex.PARI_PEAK: "Pari Peak",
    Hex.PIPERS_ENCLAVE: "Piper's Enclave",
    Hex.REACHING_TRAIL: "Reaching Trail",
    Hex.REAVERS_PASS: "Reaver's Pass",
    Hex.RED_RIVER: "Red River",
    Hex.SABLEPORT: "Sableport",
    Hex.SHACKLED_CHASM: "Shackled Chasm",
    Hex.SPEAKING_WOODS: "Speaking Woods",
    Hex.STEMA_LANDING: "Stema Landing",
    Hex.STLICAN_SHELF: "Stlican Shelf",
    Hex.STONECRADLE: "Stonecradle",
    Hex.TEMPEST_ISLAND: "Tempest Island",
    Hex.TERMINUS: "Terminus",
    Hex.THE_FINGERS: "The Fingers",
    Hex.TYRANT_FOOTHILLS: "Tyrant Foothills",
    Hex.UMBRAL_WILDWOOD: "Umbral Wildwood",
    Hex.VIPER_PIT: "Viper Pit",
    Hex.WEATHERED_EXPANSE: "Weathered Expanse",
    Hex.WESTGATE: "Westgate",
    Hex.WRESTA: "Wresta",
}

_BY_DISPLAY: dict[str, Hex] = {_normalize(name): member for member, name in _DISPLAY_NAMES.items()}
