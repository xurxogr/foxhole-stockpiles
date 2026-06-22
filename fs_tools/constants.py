"""Shared fs_tools constants."""

# Icon quantity-box scale. The quantity box is 64 px tall on a 2160 px-high
# reference frame, so its pixel size at any resolution is
# ``round(ICON_BOX_SCALE * frame_height)``. Used when adding/replacing icons and
# for the debug-image overlay.
ICON_BOX_SCALE: float = 64 / 2160
