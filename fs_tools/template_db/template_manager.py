"""Template manager for handling multiple resolution databases and icon matching."""

import asyncio
import logging
import os
import time
from collections import OrderedDict
from multiprocessing import Pool
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, cast

import cv2
import h5py
import numpy as np
from numpy.typing import NDArray

from foxhole_stockpiles.core.utils import compute_icon_phash
from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.models.database_statistics import DatabaseStatistics
from foxhole_stockpiles.models.icon_template import IconTemplate
from foxhole_stockpiles.models.match_result import MatchResult
from fs_tools.template_db.template_database import DATABASE_VERSION, TemplateDatabase

logger = logging.getLogger(__name__)

# Icon-matching tuning defaults. These are no longer user-configurable via
# settings; they are fixed here and reused by every caller of match_icon.
DEFAULT_PHASH_THRESHOLD = 15
DEFAULT_MAX_NCC_CANDIDATES = 50
DEFAULT_NCC_TIEBREAKER_THRESHOLD = 0.003


def _prepare_resolution_data(
    resolution: SupportedResolution, database: TemplateDatabase
) -> dict[str, Any]:
    """Prepare resolution data for HDF5 writing (worker function for multiprocessing).

    This function extracts all data from templates into numpy arrays,
    which can then be written to HDF5 by the main process.

    Args:
        resolution (SupportedResolution): Resolution being processed
        database (TemplateDatabase): Database to prepare

    Returns:
        dict[str, Any]: Dictionary containing prepared numpy arrays and metadata
            (various numpy dtypes including uint8, uint64, bool, object)
    """
    start_time = time.perf_counter()
    n_templates = len(database.templates)

    if n_templates == 0:
        # Return minimal data for empty database
        return {
            "resolution": resolution.value,
            "template_count": 0,
            "icon_size": 0,
            "empty": True,
        }

    logger.debug("Worker: Preparing %d templates for resolution %s", n_templates, resolution.value)

    # Get image dimensions from first template
    first_image = database.templates[0].image
    img_h, img_w, img_c = first_image.shape

    # Preallocate numpy arrays
    images = np.empty((n_templates, img_h, img_w, img_c), dtype=np.uint8)
    codes = np.empty(n_templates, dtype=object)
    mods = np.empty(n_templates, dtype=object)
    crated = np.empty(n_templates, dtype=bool)
    faction = np.empty(n_templates, dtype=np.uint8)
    category = np.empty(n_templates, dtype=np.uint8)
    phash = np.empty(n_templates, dtype=np.uint64)

    # Fill arrays
    for i, template in enumerate(database.templates):
        images[i] = template.image
        codes[i] = template.code
        mods[i] = template.mod
        crated[i] = template.crated
        faction[i] = list(ItemFaction).index(template.faction)
        category[i] = list(ItemCategory).index(template.category)
        phash[i] = template.phash

    elapsed = time.perf_counter() - start_time
    logger.debug(
        "Worker: Prepared %d templates for %s in %.2f seconds",
        n_templates,
        resolution.value,
        elapsed,
    )

    return {
        "resolution": resolution.value,
        "template_count": n_templates,
        "icon_size": img_h,
        "empty": False,
        "images": images,
        "codes": codes,
        "mods": mods,
        "crated": crated,
        "faction": faction,
        "category": category,
        "phash": phash,
    }


def _write_prepared_data_to_group(group: h5py.Group, prepared_data: dict[str, Any]) -> None:
    """Write prepared data to an HDF5 group.

    Args:
        group (h5py.Group): HDF5 group to write to
        prepared_data (dict[str, Any]): Prepared data from _prepare_resolution_data
    """
    start_time = time.perf_counter()

    # Handle empty database
    if cast(bool, prepared_data.get("empty", False)):
        group.attrs["resolution"] = prepared_data["resolution"]
        group.attrs["template_count"] = 0
        group.attrs["icon_size"] = 0
        group.attrs["version"] = DATABASE_VERSION
        group.attrs["format"] = "hdf5"
        logger.warning("Saved empty database for resolution %s", prepared_data["resolution"])
        return

    n_templates = cast(int, prepared_data["template_count"])
    img_h = cast(int, prepared_data["icon_size"])
    images = cast(NDArray[np.uint8], prepared_data["images"])
    img_w = images.shape[2]

    # Create datasets with compression
    str_dtype = h5py.string_dtype(encoding="utf-8")

    group.create_dataset(
        "images",
        data=images,
        compression="gzip",
        compression_opts=4,
    )
    group.create_dataset(
        "codes", data=cast(NDArray[np.object_], prepared_data["codes"]), dtype=str_dtype
    )
    group.create_dataset(
        "mods", data=cast(NDArray[np.object_], prepared_data["mods"]), dtype=str_dtype
    )
    group.create_dataset(
        "crated", data=cast(NDArray[np.bool_], prepared_data["crated"]), dtype=bool
    )
    group.create_dataset(
        "faction", data=cast(NDArray[np.uint8], prepared_data["faction"]), dtype=np.uint8
    )
    group.create_dataset(
        "category", data=cast(NDArray[np.uint8], prepared_data["category"]), dtype=np.uint8
    )
    group.create_dataset(
        "phash", data=cast(NDArray[np.uint64], prepared_data["phash"]), dtype=np.uint64
    )

    # Store metadata as attributes
    group.attrs["resolution"] = prepared_data["resolution"]
    group.attrs["template_count"] = n_templates
    group.attrs["icon_size"] = img_h
    group.attrs["version"] = DATABASE_VERSION
    group.attrs["format"] = "hdf5"

    elapsed = time.perf_counter() - start_time
    logger.info(
        "Saved %d templates (%dx%d) to HDF5 group %s in %.2f seconds",
        n_templates,
        img_h,
        img_w,
        group.name,
        elapsed,
    )


class TemplateManager:
    """Manages multiple resolution-specific template databases."""

    # Class-level shared LRU cache (shared across all instances)
    _shared_databases: ClassVar[OrderedDict[tuple[Path, SupportedResolution], TemplateDatabase]] = (
        OrderedDict()
    )
    _shared_lock: ClassVar[Lock] = Lock()
    _cache_size: ClassVar[int] = 16  # Default cache size

    def __init__(self, database_path: Path, cache_size: int | None = None) -> None:
        """Initialize template manager.

        Args:
            database_path (Path): Path to the binary database file
            cache_size (int | None): Maximum number of resolution databases to cache.
                If None, uses the class-level default (16). Set to 0 to disable caching.
        """
        self.database_path = database_path
        self.active_database: TemplateDatabase | None = None
        self.current_resolution: SupportedResolution | None = None

        # Store instance-level cache size (for this instance's operations)
        self.cache_size = cache_size if cache_size is not None else 16

        # Update class-level cache size if provided (for shared cache)
        if cache_size is not None and isinstance(cache_size, int):
            with self._shared_lock:
                TemplateManager._cache_size = cache_size
                # If reducing cache size, evict excess entries
                self._evict_to_size(cache_size)

    @classmethod
    def _evict_to_size(cls, max_size: int) -> None:
        """Evict least recently used entries to fit within max_size.

        Must be called with _shared_lock held.

        Args:
            max_size (int): Maximum number of entries to keep
        """
        # Protect against non-int values (e.g., mocks in tests)
        if not isinstance(max_size, int):
            return

        while len(cls._shared_databases) > max_size:
            # Remove oldest (least recently used) entry
            cls._shared_databases.popitem(last=False)
            logger.debug(
                "Evicted LRU database from cache (cache size: %d)", len(cls._shared_databases)
            )

    def _check_database_version(self, file_path: Path) -> int:
        """Check database format and return version number.

        Args:
            file_path (Path): Path to database file

        Returns:
            int: Version number (0=invalid/unknown, 2+=HDF5 with version)
        """
        try:
            # Try to open as HDF5
            with h5py.File(str(file_path), "r") as f:
                # If it's a valid HDF5 file, check for version attribute
                if "version" in f.attrs:
                    return int(f.attrs["version"])  # type: ignore[arg-type]
                # Valid HDF5 but no version attribute (shouldn't happen, but treat as v2)
                return 2
        except OSError:
            # Not a valid HDF5 file
            return 0

    def get_database_statistics(self) -> DatabaseStatistics:
        """Get database statistics without loading full template data.

        Returns:
            DatabaseStatistics: Database statistics with per-mod resolution counts

        Raises:
            FileNotFoundError: If database file not found
            ValueError: If database format is invalid
        """
        # Use existing method for validation and getting resolutions
        available_resolutions = self.get_available_resolutions()

        # Read statistics from HDF5 file - track per mod per resolution
        mod_stats: dict[str, dict[str, int]] = {}

        with h5py.File(str(self.database_path), "r") as f:
            for resolution in available_resolutions:
                group = f[resolution.value]
                if not isinstance(group, h5py.Group):
                    continue

                # Get mods for this resolution
                if "mods" in group:
                    mods_dataset = group["mods"]
                    if not isinstance(mods_dataset, h5py.Dataset):
                        continue
                    mods_data = mods_dataset[:]

                    # Count templates per mod for this resolution
                    for mod in mods_data:
                        mod_str = mod.decode("utf-8") if isinstance(mod, bytes) else str(mod)

                        if mod_str not in mod_stats:
                            mod_stats[mod_str] = {}

                        if resolution.value not in mod_stats[mod_str]:
                            mod_stats[mod_str][resolution.value] = 0

                        mod_stats[mod_str][resolution.value] += 1

        return DatabaseStatistics(
            resolutions=sorted([r.value for r in available_resolutions], key=lambda x: int(x)),
            mod_stats=mod_stats,
        )

    def get_available_resolutions(self) -> list[SupportedResolution]:
        """Get list of available resolutions in the database file.

        Returns:
            list[SupportedResolution]: List of available resolutions, sorted by value

        Raises:
            FileNotFoundError: If database file not found
            ValueError: If database format is invalid
        """
        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Template database not found: {self.database_path}\n\n"
                f"Please build a database first:\n"
                f"  fs database-builder --catalog catalog.json --templates templates/ "
                f"--database {self.database_path}"
            )

        # Check database format and version
        db_version = self._check_database_version(self.database_path)

        if db_version == 0:
            raise ValueError(
                f"Database file format is not recognized: {self.database_path}\n"
                f"File may be corrupted or in an unsupported format."
            )

        if db_version != DATABASE_VERSION:
            raise ValueError(
                f"Database version {db_version} does not match expected version "
                f"{DATABASE_VERSION}. Please regenerate using 'fs generate-templates'."
            )

        # Get available resolutions from HDF5 file
        available_resolutions = []
        with h5py.File(str(self.database_path), "r") as f:
            for resolution_key in f.keys():
                try:
                    resolution = SupportedResolution(resolution_key)
                    available_resolutions.append(resolution)
                except ValueError:
                    logger.warning("Skipping invalid resolution key: %s", resolution_key)
                    continue

        # Sort by resolution value
        available_resolutions.sort(key=lambda r: int(r.value))

        return available_resolutions

    async def load_database(self, resolution: SupportedResolution) -> TemplateDatabase:
        """Load or get cached database for specific resolution.

        Supports HDF5 format (version 2+).

        Uses LRU cache based on template_cache_size setting:
        - cache_size = 0: No caching, always load from disk
        - cache_size > 0: LRU cache with specified maximum size

        Args:
            resolution (SupportedResolution): Target resolution

        Returns:
            TemplateDatabase: Loaded template database

        Raises:
            FileNotFoundError: If database file not found
            ValueError: If database format is invalid or needs migration
        """
        cache_key = (self.database_path, resolution)

        # Get effective cache size (handle mocked values in tests)
        effective_cache_size = self.cache_size if isinstance(self.cache_size, int) else 16

        # If caching is enabled, check cache first
        if effective_cache_size > 0:
            with self._shared_lock:
                if cache_key in self._shared_databases:
                    # Move to end (mark as recently used)
                    self._shared_databases.move_to_end(cache_key)
                    logger.debug("Cache hit for resolution %s", resolution)
                    return self._shared_databases[cache_key]

        # Check if database exists
        if not self.database_path.exists():
            raise FileNotFoundError(
                f"Template database not found: {self.database_path}\n\n"
                f"Please build a database first:\n"
                f"  fs database-builder --catalog catalog.json --templates templates/ "
                f"--database {self.database_path}"
            )

        # Check database format and version
        db_version = self._check_database_version(self.database_path)

        if db_version == 0:
            raise ValueError(
                f"Database file format is not recognized: {self.database_path}\n"
                f"File may be corrupted or in an unsupported format."
            )

        if db_version != DATABASE_VERSION:
            raise ValueError(
                f"Database version {db_version} does not match expected version "
                f"{DATABASE_VERSION}. Please regenerate using 'fs generate-templates'."
            )

        # Load from HDF5 file
        logger.debug(
            "Loading template database for resolution %s from %s",
            resolution,
            self.database_path,
        )

        def load_hdf5() -> TemplateDatabase:
            """Load HDF5 file synchronously."""
            with h5py.File(str(self.database_path), "r") as f:
                # Check if resolution exists
                if resolution.value not in f:
                    available = list(f.keys())
                    raise ValueError(
                        f"Resolution {resolution.value} not found in database.\n"
                        f"Available resolutions: {', '.join(available)}"
                    )

                # Load the specific resolution group
                group = f[resolution.value]
                database = TemplateDatabase.load_from_hdf5_group(
                    group=cast(h5py.Group, group), resolution=resolution
                )

            return database

        database = await asyncio.to_thread(load_hdf5)

        # Cache if caching is enabled
        if effective_cache_size > 0:
            with self._shared_lock:
                # Add to cache
                self._shared_databases[cache_key] = database
                self._shared_databases.move_to_end(cache_key)  # Mark as most recently used

                # Evict if over limit
                if len(self._shared_databases) > effective_cache_size:
                    evicted_key = next(iter(self._shared_databases))
                    self._shared_databases.pop(evicted_key)
                    logger.debug(
                        "Evicted %s from cache (size: %d/%d)",
                        evicted_key[1],
                        len(self._shared_databases),
                        effective_cache_size,
                    )

        logger.debug(
            "Loaded database with %d templates for resolution %s%s",
            len(database.templates),
            resolution,
            " (cached)" if effective_cache_size > 0 else " (no cache)",
        )

        return database

    async def load_all_resolutions(self) -> dict[SupportedResolution, TemplateDatabase]:
        """Load all available resolutions from the database.

        Automatically sets cache size to hold all resolutions in memory.
        Useful for tools that need to browse/inspect all resolutions at once.

        Returns:
            dict[SupportedResolution, TemplateDatabase]: Dictionary mapping resolutions to databases

        Raises:
            FileNotFoundError: If database file not found
            ValueError: If database format is invalid or needs migration
        """
        start_time = time.perf_counter()

        # Get available resolutions
        available_resolutions = self.get_available_resolutions()

        # Increase cache size if needed to hold all resolutions
        # (but don't decrease it if it's already larger)
        num_resolutions = len(available_resolutions)
        if self.cache_size < num_resolutions:
            logger.debug(
                "Increasing cache size from %d to %d to hold all resolutions",
                self.cache_size,
                num_resolutions,
            )
            self.cache_size = num_resolutions

        logger.info(
            "Loading all %d resolutions from %s (cache size: %d)",
            len(available_resolutions),
            self.database_path,
            self.cache_size,
        )

        # Load all resolutions
        all_databases: dict[SupportedResolution, TemplateDatabase] = {}
        for resolution in available_resolutions:
            database = await self.load_database(resolution)
            all_databases[resolution] = database

        elapsed = time.perf_counter() - start_time
        total_templates = sum(len(db.templates) for db in all_databases.values())

        logger.info(
            "Loaded all %d resolutions (%d total templates) in %.2f seconds",
            len(all_databases),
            total_templates,
            elapsed,
        )

        return all_databases

    async def set_active_resolution(self, screenshot_height: int) -> SupportedResolution:
        """Set active resolution based on screenshot dimensions.

        Args:
            screenshot_height (int): Height of the screenshot in pixels

        Returns:
            SupportedResolution: Selected resolution for processing
        """
        # Find exact or closest resolution
        target_resolution = self._find_best_resolution(height=screenshot_height)

        if self.current_resolution != target_resolution:
            logger.debug(
                "Switching to resolution %s for screenshot height %d",
                target_resolution,
                screenshot_height,
            )
            self.active_database = await self.load_database(resolution=target_resolution)
            self.current_resolution = target_resolution

        return target_resolution

    def _find_best_resolution(self, height: int) -> SupportedResolution:
        """Find the best matching resolution for given height.

        Args:
            height (int): Screenshot height in pixels

        Returns:
            SupportedResolution: Best matching resolution
        """
        resolutions = [int(r.value) for r in SupportedResolution]

        # Find exact match first
        if str(height) in [r.value for r in SupportedResolution]:
            return SupportedResolution(str(height))

        # Find closest resolution
        closest = min(resolutions, key=lambda x: abs(x - height))
        return SupportedResolution(str(closest))

    def match_icon(
        self,
        icon_image: NDArray[np.uint8] | None = None,
        faction: ItemFaction | None = None,
        mod: str | None = None,
        category: ItemCategory | None = None,
        crated: bool | None = None,
        code: str | None = None,
        excluded_codes: list[str] | None = None,
        phash_threshold: int = DEFAULT_PHASH_THRESHOLD,
        max_ncc_candidates: int = DEFAULT_MAX_NCC_CANDIDATES,
        early_exit_threshold: float = 0.0,
        confidence_gap: float = 0.0,
        ncc_tiebreaker_threshold: float = DEFAULT_NCC_TIEBREAKER_THRESHOLD,
        top_n: int = 5,
    ) -> MatchResult:
        """Get candidates and optionally perform icon matching.

        Args:
            icon_image (NDArray[np.uint8] | None): Optional icon image to match
            faction (ItemFaction | None): Optional faction filter
            mod (str | None): Optional mod filter
            category (ItemCategory | None): Optional category filter
            crated (bool | None): Optional crated filter
            code (str | None): Optional item code filter
            excluded_codes (list[str] | None): Optional list of item codes to exclude from matching
            phash_threshold (int): Maximum Hamming distance for pHash filtering
            max_ncc_candidates (int): Maximum candidates for NCC optimization
            early_exit_threshold (float): Confidence threshold for immediate exit (0.0 = disabled)
            confidence_gap (float): Gap for returning alternative candidates (0.0 = disabled)
            ncc_tiebreaker_threshold (float): When top matches are within this threshold,
                use pixel difference as tiebreaker (0.0 = disabled)
            top_n (int): Number of top matches to return with confidence scores (default: 5)

        Returns:
            MatchResult: Candidates list and optional icon match result
        """
        if not self.active_database:
            raise ValueError("No active database loaded")

        # Get candidates using filters
        candidates = self.active_database.get_candidates(
            faction=faction,
            mod=mod,
            category=category,
            crated=crated,
            code=code,
            excluded_codes=excluded_codes,
        )

        icon_result = None
        confidence_result: float = 0.0

        if icon_image is None:
            return MatchResult(
                candidates=candidates, icon=None, confidence=0.0, tested_candidates=0
            )

        start_time = time.perf_counter()

        # pHash pre-filtering
        final_candidates = candidates
        phash_time_ms = 0.0

        if len(candidates) > max_ncc_candidates:
            phash_start = time.perf_counter()
            icon_phash = compute_icon_phash(icon_image)

            # Vectorized phash distance computation
            distances = self.active_database.get_phash_distances(icon_phash, candidates)

            # Filter candidates within threshold
            mask = distances <= phash_threshold
            filtered_indices = np.where(mask)[0]

            # Get candidate indices and distances for filtered items
            filtered_candidates = [candidates[i] for i in filtered_indices]
            filtered_distances = distances[filtered_indices]

            # Sort by distance and take top candidates
            sort_order = np.argsort(filtered_distances)
            final_candidates = [filtered_candidates[i] for i in sort_order[:max_ncc_candidates]]

            phash_time_ms = (time.perf_counter() - phash_start) * 1000

        # Template matching
        ncc_start = time.perf_counter()
        best_match = None
        best_confidence = 0.0
        candidates_tested = 0
        all_matches: list[tuple[float, IconTemplate]] = []

        for candidate_idx in final_candidates:
            candidates_tested += 1
            template = self.active_database.templates[candidate_idx]

            result = cv2.matchTemplate(
                image=icon_image, templ=cast(cv2.Mat, template.image), method=cv2.TM_CCOEFF_NORMED
            )
            _, confidence, _, _ = cv2.minMaxLoc(result)

            # Store all matches for top N
            all_matches.append((confidence, template))

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = template

            # Early exit if very high confidence found (only if early_exit_threshold > 0)
            if early_exit_threshold > 0.0 and confidence >= early_exit_threshold:
                logger.debug(
                    "Early exit: found %.3f confidence (>= %.3f) after testing %d candidates",
                    confidence,
                    early_exit_threshold,
                    candidates_tested,
                )
                break

        # Sort all matches by confidence and get top N
        all_matches.sort(key=lambda x: x[0], reverse=True)

        # Apply tiebreaker if enabled and top matches are very close
        if (
            ncc_tiebreaker_threshold > 0.0
            and icon_image is not None
            and len(all_matches) > 1
            and best_match is not None
        ):
            # Find matches within tiebreaker threshold of best
            close_matches = [
                (conf, t)
                for conf, t in all_matches
                if best_confidence - conf <= ncc_tiebreaker_threshold
            ]

            if len(close_matches) > 1:
                # Compute edge-based difference for close matches
                # Edge comparison is gamma-invariant (local contrast, not absolute brightness)
                icon_gray = cv2.cvtColor(icon_image, cv2.COLOR_BGR2GRAY)
                icon_edges = cv2.Sobel(icon_gray, cv2.CV_32F, 1, 1)

                scored: list[tuple[float, float, IconTemplate]] = []
                for conf, template in close_matches:
                    template_gray = cv2.cvtColor(template.image, cv2.COLOR_BGR2GRAY)
                    template_edges = cv2.Sobel(template_gray, cv2.CV_32F, 1, 1)
                    edge_diff = float(np.mean(np.abs(icon_edges - template_edges)))
                    scored.append((edge_diff, conf, template))

                # Sort by pixel diff (lower = better match)
                scored.sort(key=lambda x: x[0])

                # Update best match if tiebreaker changed the winner
                if scored[0][2].code != best_match.code:
                    logger.debug(
                        "Tiebreaker changed match from %s (%.4f) to %s (%.4f, pixel_diff=%.2f)",
                        best_match.code,
                        best_confidence,
                        scored[0][2].code,
                        scored[0][1],
                        scored[0][0],
                    )
                    best_match = scored[0][2]
                    best_confidence = scored[0][1]

        top_matches = [(template, conf) for conf, template in all_matches[:top_n]]

        # Calculate gap candidates if confidence_gap > 0
        gap_candidates: list[tuple[IconTemplate, float]] = []
        if confidence_gap > 0.0 and best_match and best_confidence > 0.0:
            min_confidence = best_confidence - confidence_gap

            for conf, template in all_matches:
                # Skip if it's the best match itself
                if template.code == best_match.code and template.crated == best_match.crated:
                    continue

                # Only include candidates within the gap that match category, crated, and mod
                if (
                    conf >= min_confidence
                    and conf < best_confidence
                    and template.category == best_match.category
                    and template.crated == best_match.crated
                    and template.mod == best_match.mod
                ):
                    gap_candidates.append((template, conf))

            # Sort gap candidates by confidence (highest first)
            gap_candidates.sort(key=lambda x: x[1], reverse=True)

            if gap_candidates:
                logger.debug(
                    "Found %d gap candidates within %.3f of best match (%.3f)",
                    len(gap_candidates),
                    confidence_gap,
                    best_confidence,
                )

        ncc_time_ms = (time.perf_counter() - ncc_start) * 1000
        end_time = time.perf_counter()
        total_time_ms = (end_time - start_time) * 1000

        logger.debug(
            "Icon matching took %.2f ms total (pHash: %.2f, NCC: %.2f) tested %d of %d candidates.",
            total_time_ms,
            phash_time_ms,
            ncc_time_ms,
            candidates_tested,
            len(final_candidates),
        )

        # Always return the best match regardless of confidence
        if best_match:
            icon_result = best_match
            confidence_result = best_confidence

        return MatchResult(
            candidates=candidates,
            icon=icon_result,
            confidence=confidence_result,
            best_match=best_match,
            best_confidence=best_confidence,
            tested_candidates=candidates_tested,
            top_matches=top_matches,
            gap_candidates=gap_candidates,
        )

    @staticmethod
    def save_databases_to_hdf5(
        databases: dict[SupportedResolution, TemplateDatabase],
        output_path: Path,
        workers: int | None = None,
    ) -> None:
        """Save multiple resolution databases to a single HDF5 file.

        Args:
            databases (dict[SupportedResolution, TemplateDatabase]): Databases to save
            output_path (Path): Output file path
            workers (int | None): Number of worker processes for parallel data preparation.
                If None, uses os.cpu_count(). Set to 1 to disable multiprocessing.

        Raises:
            ValueError: If databases dict is empty
        """
        if not databases:
            raise ValueError("Cannot save empty databases dictionary")

        logger.debug("Saving %d resolution(s) to HDF5 file: %s", len(databases), output_path)

        # Invalidate cache for this database file to ensure fresh loads
        with TemplateManager._shared_lock:
            # Remove all cache entries for this database path
            keys_to_remove = [
                key for key in TemplateManager._shared_databases if key[0] == output_path
            ]
            for key in keys_to_remove:
                TemplateManager._shared_databases.pop(key, None)
            if keys_to_remove:
                logger.debug(
                    "Invalidated %d cached database entries for %s",
                    len(keys_to_remove),
                    output_path,
                )

        # Determine number of workers
        if workers is None:
            workers = os.cpu_count() or 1
        workers = max(1, min(workers, len(databases)))  # Cap at number of databases

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare data (in parallel if multiple workers, sequentially otherwise)
        prep_start = time.perf_counter()
        items = list(databases.items())

        if workers > 1 and len(databases) > 1:
            logger.debug("Preparing data with %d worker processes", workers)
            with Pool(processes=workers) as pool:
                prepared_data = pool.starmap(_prepare_resolution_data, items)
        else:
            logger.debug("Preparing data with single worker")
            prepared_data = [_prepare_resolution_data(res, db) for res, db in items]

        prep_time = time.perf_counter() - prep_start
        logger.info("Data preparation time: %.2f seconds", prep_time)

        # Write prepared data to HDF5 sequentially (always use efficient bulk write)
        write_start = time.perf_counter()
        with h5py.File(str(output_path), "w") as f:
            # Store database-level metadata
            f.attrs["version"] = DATABASE_VERSION
            f.attrs["format"] = "hdf5"
            f.attrs["resolutions"] = [r.value for r in databases.keys()]

            # Write each resolution's prepared data
            for (resolution, _), prep_data in zip(items, prepared_data, strict=True):
                group = f.create_group(resolution.value)
                _write_prepared_data_to_group(group, prep_data)

        write_time = time.perf_counter() - write_start
        logger.info("HDF5 write time: %.2f seconds", write_time)

        logger.debug(
            "Saved %d resolution(s) to %s (%.1f MB)",
            len(databases),
            output_path,
            output_path.stat().st_size / (1024 * 1024),
        )

    @staticmethod
    def save_single_resolution(
        database: TemplateDatabase,
        resolution: SupportedResolution,
        output_path: Path,
    ) -> None:
        """Save a single resolution database to an existing HDF5 file.

        This is faster than save_databases_to_hdf5 when only one resolution was modified.

        Args:
            database (TemplateDatabase): Database to save
            resolution (SupportedResolution): Resolution being saved
            output_path (Path): Output file path (must exist)

        Raises:
            FileNotFoundError: If output file doesn't exist
        """
        if not output_path.exists():
            raise FileNotFoundError(f"Database file not found: {output_path}")

        logger.debug("Saving single resolution %s to HDF5 file: %s", resolution.value, output_path)

        # Invalidate cache for this resolution
        with TemplateManager._shared_lock:
            cache_key = (output_path, resolution)
            if cache_key in TemplateManager._shared_databases:
                TemplateManager._shared_databases.pop(cache_key, None)
                logger.debug("Invalidated cache for %s/%s", output_path, resolution.value)

        # Prepare data for this resolution
        prep_start = time.perf_counter()
        prepared_data = _prepare_resolution_data(resolution, database)
        prep_time = time.perf_counter() - prep_start
        logger.debug("Data preparation time: %.3f seconds", prep_time)

        # Update HDF5 file
        write_start = time.perf_counter()
        with h5py.File(str(output_path), "a") as f:
            # Delete existing group if it exists
            if resolution.value in f:
                del f[resolution.value]

            # Create new group with updated data
            group = f.create_group(resolution.value)
            _write_prepared_data_to_group(group, prepared_data)

        write_time = time.perf_counter() - write_start
        logger.debug("HDF5 write time: %.3f seconds", write_time)

    def __repr__(self) -> str:
        """String representation of the template manager."""
        return (
            f"TemplateManager(database_path={self.database_path}, "
            f"loaded_resolutions={len(self._shared_databases)}, "
            f"current_resolution={self.current_resolution})"
        )
