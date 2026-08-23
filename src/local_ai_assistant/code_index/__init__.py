from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import CodeRAG

__all__ = ["CodeRAG"]


def __getattr__(name: str):
    if name == "CodeRAG":
        from .repository import CodeRAG

        return CodeRAG
    raise AttributeError(name)
