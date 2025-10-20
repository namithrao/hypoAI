"""
Agent 4: Dataset Builder

Loads, harmonizes, and joins NHANES data files across multiple cycles.
Handles missing data and variable inconsistencies.
"""

import logging
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from nhanes_data.nhanes_data_api import NHANESDataAPI

from .models import DataAssemblySpec, DataFileSpec

logger = logging.getLogger(__name__)


class DatasetBuilderAgent:
    """
    Builds harmonized datasets from NHANES data files.

    Responsibilities:
    - Load data files from multiple cycles
    - Join files on SEQN (subject ID)
    - Harmonize variables across cycles
    - Handle missing data
    - Apply population filters
    """

    def __init__(self, data_directory: str = "./data/nhanes"):
        self.nhanes_api = NHANESDataAPI(data_directory=data_directory)

    async def build_dataset(
        self,
        assembly_spec: DataAssemblySpec,
        population_filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Build complete dataset from assembly specification.

        Args:
            assembly_spec: Data assembly specification from Agent 3
            population_filters: Optional filters (age, sex, etc.)

        Returns:
            Pandas DataFrame with harmonized multi-cycle data

        Workflow:
            1. Load data for each cycle
            2. Harmonize variables across cycles
            3. Concatenate cycles
            4. Apply population filters
            5. Handle missing data
        """
        logger.info(f"Building dataset from {len(assembly_spec.cycles)} cycles, "
                   f"{len(assembly_spec.data_files)} file groups")

        all_cycle_data = []

        for cycle in assembly_spec.cycles:
            logger.info(f"Processing cycle: {cycle}")

            cycle_data = await self._load_cycle_data(cycle, assembly_spec)

            if cycle_data is not None and not cycle_data.empty:
                # Add cycle identifier
                cycle_data["NHANES_CYCLE"] = cycle
                all_cycle_data.append(cycle_data)
            else:
                logger.warning(f"No data loaded for cycle {cycle}")

        if not all_cycle_data:
            raise ValueError("No data loaded from any cycle")

        # Concatenate all cycles
        logger.info(f"Concatenating {len(all_cycle_data)} cycle datasets")
        combined_data = pd.concat(all_cycle_data, axis=0, ignore_index=True)
        logger.info(f"Combined dataset shape: {combined_data.shape}")

        # Apply population filters
        if population_filters:
            combined_data = self._apply_population_filters(combined_data, population_filters)
            logger.info(f"After population filters: {combined_data.shape}")

        # Handle missing data
        combined_data = self._handle_missing_data(combined_data, assembly_spec)
        logger.info(f"After missing data handling: {combined_data.shape}")

        # Add metadata
        combined_data.attrs["source"] = "NHANES"
        combined_data.attrs["cycles"] = assembly_spec.cycles
        combined_data.attrs["assembly_spec"] = assembly_spec.model_dump()

        return combined_data

    async def _load_cycle_data(
        self,
        cycle: str,
        assembly_spec: DataAssemblySpec
    ) -> Optional[pd.DataFrame]:
        """
        Load and join all required data files for a single cycle.

        Returns DataFrame with all variables joined on SEQN.
        """
        cycle_dfs = []

        for file_spec in assembly_spec.data_files:
            try:
                df = await self._load_file(cycle, file_spec, assembly_spec)
                if df is not None and not df.empty:
                    cycle_dfs.append(df)
            except Exception as e:
                logger.error(f"Failed to load {file_spec.file_name} for {cycle}: {e}")
                continue

        if not cycle_dfs:
            return None

        # Join all dataframes on SEQN
        merged = cycle_dfs[0]
        for df in cycle_dfs[1:]:
            merged = merged.merge(df, on="SEQN", how=assembly_spec.join_strategy, suffixes=("", "_dup"))

            # Remove duplicate columns (from join conflicts)
            dup_cols = [col for col in merged.columns if col.endswith("_dup")]
            if dup_cols:
                logger.warning(f"Dropping duplicate columns: {dup_cols}")
                merged = merged.drop(columns=dup_cols)

        return merged

    async def _load_file(
        self,
        cycle: str,
        file_spec: DataFileSpec,
        assembly_spec: DataAssemblySpec
    ) -> Optional[pd.DataFrame]:
        """
        Load a single NHANES data file.

        Handles:
        - Variable selection
        - Uncommon variable availability
        - Error handling
        """
        # Check if file exists for this cycle
        if cycle not in file_spec.cycle_mapping:
            logger.warning(f"File {file_spec.file_name} not available in {cycle}")
            return None

        actual_filename = file_spec.cycle_mapping[cycle]

        # Determine which variables to request
        # For now, we request all variables since NHANES PyTool doesn't expose
        # variable-level metadata easily. In production, you'd want to:
        # 1. Download the file once to inspect column names
        # 2. Map concept names to actual NHANES variable codes
        # 3. Use specific_variables parameter

        # For this implementation, we'll load all variables and filter afterward
        try:
            logger.info(f"Loading {file_spec.data_category}/{actual_filename} for {cycle}")

            df = self.nhanes_api.retrieve_data(
                data_category=file_spec.data_category,
                cycle=cycle,
                filename=file_spec.file_name,
                include_uncommon_variables=True,
                specific_variables=None  # Load all variables
            )

            if df is None or df.empty:
                logger.warning(f"Empty data returned for {file_spec.file_name}")
                return None

            logger.info(f"Loaded {df.shape[0]} rows, {df.shape[1]} columns")

            # Filter to only requested variables (plus SEQN)
            # This requires mapping concept names to actual column names
            # For now, keep all columns and let downstream processing handle it

            return df

        except Exception as e:
            logger.error(f"Error loading {file_spec.file_name} from {cycle}: {e}")
            return None

    def _apply_population_filters(
        self,
        df: pd.DataFrame,
        filters: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Apply population filters to dataset.

        Filters can include:
        - age_min, age_max
        - sex
        - race
        - conditions (requires, excludes)
        """
        filtered = df.copy()
        initial_count = len(filtered)

        # Age filter
        # NHANES age variable is typically RIDAGEYR
        if "age_min" in filters and "RIDAGEYR" in filtered.columns:
            filtered = filtered[filtered["RIDAGEYR"] >= filters["age_min"]]
            logger.info(f"Age >= {filters['age_min']}: {len(filtered)} rows")

        if "age_max" in filters and "RIDAGEYR" in filtered.columns:
            filtered = filtered[filtered["RIDAGEYR"] <= filters["age_max"]]
            logger.info(f"Age <= {filters['age_max']}: {len(filtered)} rows")

        # Sex filter
        # NHANES sex variable is typically RIAGENDR (1=Male, 2=Female)
        if "sex" in filters and "RIAGENDR" in filtered.columns:
            if filters["sex"] == "male":
                filtered = filtered[filtered["RIAGENDR"] == 1]
            elif filters["sex"] == "female":
                filtered = filtered[filtered["RIAGENDR"] == 2]
            logger.info(f"Sex filter: {len(filtered)} rows")

        # Pregnancy exclusion
        # Check for pregnancy indicator variables
        if "exclude_pregnant" in filters and filters["exclude_pregnant"]:
            pregnancy_vars = [col for col in filtered.columns if "PREG" in col.upper()]
            for preg_var in pregnancy_vars:
                # Exclude if pregnancy indicator is positive
                filtered = filtered[~(filtered[preg_var] == 1)]

        logger.info(f"Population filtering: {initial_count} -> {len(filtered)} rows "
                   f"({100 * len(filtered) / initial_count:.1f}% retained)")

        return filtered

    def _handle_missing_data(
        self,
        df: pd.DataFrame,
        assembly_spec: DataAssemblySpec
    ) -> pd.DataFrame:
        """
        Handle missing data in the dataset.

        Strategies:
        1. Drop rows with missing outcome variable
        2. For exposures and covariates, apply imputation or flagging
        3. Report missingness patterns
        """
        initial_count = len(df)

        # Analyze missingness
        missing_report = {}
        for col in df.columns:
            missing_pct = 100 * df[col].isna().sum() / len(df)
            if missing_pct > 0:
                missing_report[col] = missing_pct

        if missing_report:
            logger.info("Variables with missing data:")
            for col, pct in sorted(missing_report.items(), key=lambda x: -x[1])[:10]:
                logger.info(f"  {col}: {pct:.1f}% missing")

        # Strategy: For now, use listwise deletion (drop rows with ANY missing data)
        # In production, you'd want more sophisticated imputation
        cleaned = df.dropna()

        logger.info(f"Missing data handling: {initial_count} -> {len(cleaned)} rows "
                   f"({100 * len(cleaned) / initial_count:.1f}% retained)")

        # If too much data lost, warn user
        if len(cleaned) < 0.5 * initial_count:
            logger.warning(f"More than 50% of data lost due to missingness. "
                          f"Consider imputation strategies.")

        return cleaned

    def get_variable_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate summary statistics for the dataset.

        Returns dictionary with summary info for each variable.
        """
        summary = {}

        for col in df.columns:
            if col == "SEQN" or col == "NHANES_CYCLE":
                continue

            col_data = df[col]
            col_summary = {
                "dtype": str(col_data.dtype),
                "count": int(col_data.notna().sum()),
                "missing": int(col_data.isna().sum()),
                "missing_pct": float(100 * col_data.isna().sum() / len(df))
            }

            # Numeric variables
            if pd.api.types.is_numeric_dtype(col_data):
                col_summary.update({
                    "mean": float(col_data.mean()) if col_data.notna().any() else None,
                    "std": float(col_data.std()) if col_data.notna().any() else None,
                    "min": float(col_data.min()) if col_data.notna().any() else None,
                    "max": float(col_data.max()) if col_data.notna().any() else None,
                    "median": float(col_data.median()) if col_data.notna().any() else None
                })

            # Categorical variables
            else:
                value_counts = col_data.value_counts()
                col_summary.update({
                    "unique_values": int(col_data.nunique()),
                    "top_values": {str(k): int(v) for k, v in value_counts.head(5).items()}
                })

            summary[col] = col_summary

        return summary
