# password/storages/__init__.py
# Concrete storage implementations

from .postgresql import PostgreSQLStorage

__all__ = ["PostgreSQLStorage"]
