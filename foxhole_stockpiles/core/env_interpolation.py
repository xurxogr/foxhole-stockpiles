import os
import re
from configparser import ExtendedInterpolation


class EnvInterpolation(ExtendedInterpolation):
    def _expandvars(self, path: str, pattern: str) -> str:
        """
        Expand shell variables of form ${var}. Unknown variables are left unchanged
        unless they came in the form ${var@defaultvalue} then defaultvalue is used.

        Args:
            path (str): The path to expand
            pattern (str): The regular expression pattern to match
            operation (str): The operation to perform

        Returns:
            str: The expanded path
        """

        pattern = re.compile(pattern, re.ASCII)
        i = 0
        while True:
            m = pattern.search(path, i)
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

    def before_read(self, parser, section, option, value):
        """
        Override the before_read method to expand environment variables and b64 decode values
        """
        value = super().before_read(parser, section, option, value)
        return self._expandvars(value, r"\$\{([^@\}]*)[@]?([^}]*)\}")
