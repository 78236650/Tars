"""Layer2 shared data spine — datasource access for all data platform modules."""

from .models import ResultSet
from .spine import fetch_rows, list_datasource_tables

__all__ = ["ResultSet", "fetch_rows", "list_datasource_tables"]
