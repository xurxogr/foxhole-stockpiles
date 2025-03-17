"""SingletonMeta Module."""

from typing import Any, ClassVar, Type


class SingletonMeta(type):
    """Singleton metaclass."""

    _instances: ClassVar[dict[Type, Any]] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Call method.

        Return the instance of the class if it exists. Otherwise, create a new
        instance and return it.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
