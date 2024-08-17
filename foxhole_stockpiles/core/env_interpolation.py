import base64
from configparser import ExtendedInterpolation
import os
import re


class EnvInterpolation(ExtendedInterpolation):
    ENVIRONMENT = 'environment'
    B64DECODE = 'b64decode'

    def _expandvars(self, path: str, pattern: str, operation: str) -> str:
        """
        Expands variables depending on the operation:
        'environment':
                Expand shell variables of form ${var}. Unknown variables are left unchanged
                unless they came in the form ${var@defaultvalue} then defaultvalue is used.
        'b64decode':
                Replace b64{XXX} with the b64 decoded value of XXX

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

            if operation == EnvInterpolation.ENVIRONMENT:
                name = m.group(1)
                default = m.group(2)
                value = os.environ.get(name) or default
            elif operation == EnvInterpolation.B64DECODE:
                value = base64.b64decode(m.group(1) + '======').decode('utf-8')
            else:
                value = None

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
        envvars = self._expandvars(value, r'\$\{([^@\}]*)[@]?([^}]*)\}', self.ENVIRONMENT)
        b64vars = self._expandvars(envvars, r'b64\{([^\}]*)\}', self.B64DECODE)
        return b64vars
