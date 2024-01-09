from configparser import ExtendedInterpolation
import os
import re


class EnvInterpolation(ExtendedInterpolation):

    def _expandvars(self, value: str) -> str:
        """
            Expand shell variables of form ${var}. Unknown variables are left unchanged
            unless they came in the form ${var@defaultvalue} then defaultvalue is used.
        :param value: str = Value to expand.
        """
        pattern = re.compile(r'\$\{([^@\}]*)[@]?([^}]*)\}', re.ASCII)
        i = 0
        while True:
            m = pattern.search(value, i)
            if not m:
                break
            i, j = m.span(0)

            name = m.group(1)
            default = m.group(2)
            env = os.environ.get(name) or default

            if env is None:
                i = j
            else:
                tail = value[j:]
                value = value[:i] + env
                i = len(value)
                value += tail

        return value

    def before_read(self, parser, section, option, value):
        value = super().before_read(parser, section, option, value)
        return self._expandvars(value)
