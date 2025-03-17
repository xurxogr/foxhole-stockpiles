"""Interpolation module for environment variables in config files."""

import os
import re
from configparser import ExtendedInterpolation
from typing import Any


class EnvInterpolation(ExtendedInterpolation):
    """Interpolation class for environment variables in config files."""

    def _expandvars(self, path: str, pattern: str) -> str:
        """Exapand shell variables in the path.

        Expand shell variables of form ${var}. Unknown variables are left unchanged
        unless they came in the form ${var@defaultvalue} then defaultvalue is used.

        Args:
            path (str): The path to expand
            pattern (str): The regular expression pattern to match
            operation (str): The operation to perform

        Returns:
            str: The expanded path
        """
        pattern_ = re.compile(pattern, re.ASCII)
        i = 0
        while True:
            m = pattern_.search(path, i)
            if not m:
                break
            i, j = m.span(0)

            name = m.group(1)
            default = m.group(2)
            value = os.environ.get(name) or default

            if value is None:
                i = j
            else:
                tail = path[j:]
                path = path[:i] + value
                i = len(path)
                path += tail

        return path

    def before_read(self, parser: Any, section: str, option: str, value: str) -> str:
        """Override the before_read method.

        Expand environment variables and b64 decode values.

        Args:
            parser (_Parser): The parser
            section (str): The section
            option (str): The option
            value (str): The value

        Returns:
            str: The expanded value
        """
        value = super().before_read(parser=parser, section=section, option=option, value=value)
        return self._expandvars(value, r"\$\{([^@\}]*)[@]?([^}]*)\}")
