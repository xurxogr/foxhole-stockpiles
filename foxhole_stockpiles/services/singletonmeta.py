"""SingletonMeta Module."""


class SingletonMeta(type):
    """Singleton metaclass."""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """Call method.

        Return the instance of the class if it exists. Otherwise, create a new
        instance and return it.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]
