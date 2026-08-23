from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repository import CodeRAG
    from .symbol_index import SymbolIndex

__all__ = ["CodeRAG", "SymbolIndex"]


def __getattr__(name: str):
    if name == "CodeRAG":
        from .repository import CodeRAG

        return CodeRAG
    if name == "SymbolIndex":
        from .symbol_index import SymbolIndex

        return SymbolIndex
    raise AttributeError(name)
