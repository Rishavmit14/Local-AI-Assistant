"""Fixture module documentation."""

import os

from .helpers import utility


def registry(name):
    return lambda value: value


def duplicate(value: int) -> int:
    """Top-level duplicate name."""
    return utility(value)


async def fetch(
    client,
    resource: str,
) -> str:
    return await client.get(resource)


@registry("service")
class Service:
    """A decorated service."""

    @staticmethod
    def duplicate(value):
        return duplicate(value)

    class Nested:
        def method(self):
            def inner():
                return os.getcwd()

            return inner()
