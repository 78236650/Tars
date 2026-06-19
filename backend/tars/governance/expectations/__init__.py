"""Great Expectations engine wrapper — zero-config, pure in-memory validation.

Usage:
    engine = GEQualityEngine()
    suite = engine.create_suite("my_suite", [
        {"type": "expect_column_values_to_not_be_null", "kwargs": {"column": "id"}},
        {"type": "expect_column_values_to_be_between", "kwargs": {"column": "age", "min_value": 0, "max_value": 150}},
    ])
    result = engine.validate(suite, pd.DataFrame(...))
    # result = {success: bool, statistics: {...}, results: [...]}
"""

from __future__ import annotations

import pandas as pd
import great_expectations as gx
from great_expectations.core import ExpectationSuite, ExpectationConfiguration


class GEQualityEngine:
    """Thin wrapper around Great Expectations EphemeralDataContext.

    No file system, no database, no external services — pure in-memory validation.
    Works offline with just `pip install great_expectations`.
    """

    def __init__(self):
        self._context = gx.get_context()  # EphemeralDataContext
        self._datasource = self._context.sources.add_pandas("tars_ds")
        self._asset_counter = 0

    @property
    def context(self):
        return self._context

    def create_suite(self, name: str, expectations: list[dict]) -> ExpectationSuite:
        """Create a GE ExpectationSuite from a list of dict definitions.

        Args:
            name: Suite name.
            expectations: List of {"type": "...", "kwargs": {...}}.

        Returns:
            ExpectationSuite ready for validation.
        """
        suite = ExpectationSuite(expectation_suite_name=name)
        for exp in expectations:
            suite.add_expectation(ExpectationConfiguration(
                expectation_type=exp["type"],
                kwargs=exp.get("kwargs", {}),
            ))
        self._context.add_expectation_suite(expectation_suite=suite)
        return suite

    def validate(self, suite: ExpectationSuite, data: pd.DataFrame) -> dict:
        """Run validation on a DataFrame against an ExpectationSuite.

        Returns a clean dict (no GE internals leaked):
          {
            "success": bool,
            "statistics": {"evaluated_expectations": int, "successful_expectations": int, ...},
            "results": [{"type": str, "success": bool, "result": dict}]
          }
        """
        self._asset_counter += 1
        asset = self._datasource.add_dataframe_asset(f"tars_batch_{self._asset_counter}")
        batch_request = asset.build_batch_request(dataframe=data)

        validator = self._context.get_validator(
            batch_request=batch_request,
            expectation_suite=suite,
        )
        result = validator.validate()

        return {
            "success": result.success,
            "statistics": result.statistics,
            "results": [
                {
                    "type": r.expectation_config.expectation_type,
                    "success": r.success,
                    "result": r.result,
                }
                for r in result.results
            ],
        }

    def profile(self, data: pd.DataFrame, columns: list[str] | None = None) -> list[dict]:
        """Auto-profile a DataFrame and suggest Expectations.

        Returns list of {"type": str, "kwargs": dict} suitable for create_suite().
        """
        if columns is None:
            columns = list(data.columns)

        suggestions: list[dict] = []

        for col in columns:
            series = data[col]
            dtype = series.dtype

            if series.isna().all():
                continue

            if series.notna().any():
                suggestions.append({
                    "type": "expect_column_values_to_not_be_null",
                    "kwargs": {"column": col},
                })

            if pd.api.types.is_numeric_dtype(dtype):
                clean = series.dropna()
                if len(clean) > 0:
                    suggestions.append({
                        "type": "expect_column_values_to_be_between",
                        "kwargs": {
                            "column": col,
                            "min_value": float(clean.min()),
                            "max_value": float(clean.max()),
                        },
                    })

            if dtype == "object" and series.nunique() <= 20:
                vals = series.dropna().unique().tolist()
                if len(vals) <= 10:
                    suggestions.append({
                        "type": "expect_column_values_to_be_in_set",
                        "kwargs": {
                            "column": col,
                            "value_set": vals,
                        },
                    })

        return suggestions
