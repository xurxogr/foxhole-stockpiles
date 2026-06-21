"""Template database tooling for fs_tools.

Build-time and inspection layer over the HDF5 template database: the database
reader/writer, the higher-level manager (matching, statistics, icon retrieval),
and the icon import helper. Only ``fs_tools`` (which builds the database) and the
Rust ``fs-ocr`` engine (which consumes it at scan time) know this format; the
``foxhole_stockpiles`` runtime must not import from here.
"""

from fs_tools.template_db.icon_manager import IconManager
from fs_tools.template_db.template_database import DATABASE_VERSION, TemplateDatabase
from fs_tools.template_db.template_manager import TemplateManager

__all__ = [
    "DATABASE_VERSION",
    "IconManager",
    "TemplateDatabase",
    "TemplateManager",
]
