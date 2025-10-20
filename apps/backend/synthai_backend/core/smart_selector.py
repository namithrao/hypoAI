"""
Smart Data Selector - AI-powered query parsing and data source selection.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from synthai_mcp_client import MCPClient

from ..config import settings
from ..models import (
    AssemblyResult,
    DataSource,
    DataSourceRanking,
    QueryParsing,
    ResearchConstraints,
    ResearchQuery,
)

logger = logging.getLogger(__name__)


class SmartDataSelector:
    """
    AI-powered data selector that parses natural language queries
    and selects optimal data sources.
    """

    def __init__(self):
        self.mcp_client: Optional[MCPClient] = None
        self._nhanes_dict = self._load_nhanes_dict()

    def _load_nhanes_dict(self) -> Dict[str, Any]:
        """Load NHANES variable dictionary."""
        try:
            # Import the dictionary from the package
            import sys
            import os

            # Add the nhanes-dict package to path
            dict_path = os.path.join(os.path.dirname(__file__), "../../../packages/nhanes-dict")
            if dict_path not in sys.path:
                sys.path.insert(0, dict_path)

            # Load the dictionary data
            with open(os.path.join(dict_path, "nhanes-variables.json"), "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load NHANES dictionary: {e}")
            return {}

    async def __aenter__(self):
        """Async context manager entry."""
        self.mcp_client = MCPClient(
            tool_paths=settings.mcp_tool_paths,
            timeout=settings.mcp_tool_timeout
        )
        await self.mcp_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.mcp_client:
            await self.mcp_client.__aexit__(exc_type, exc_val, exc_tb)

    async def process_query(self, query: ResearchQuery) -> AssemblyResult:
        """
        Process a research query and return assembled dataset information.

        Args:
            query: Research query with natural language question and constraints

        Returns:
            AssemblyResult with parsed query, source rankings, and dataset info
        """
        logger.info(f"Processing research query: {query.question}")

        # Parse the natural language query
        parsing = await self._parse_query(query.question)

        # Rank available data sources
        source_rankings = await self._rank_sources(parsing, query.constraints)

        # Select optimal sources
        selected_sources = self._select_sources(source_rankings, query.preferred_sources)

        # Assemble dataset from selected sources
        assembly_info = await self._assemble_dataset(
            parsing, selected_sources, query.constraints
        )

        # Check if synthetic data is recommended
        synthetic_rec = self._evaluate_synthetic_need(assembly_info, parsing)

        return AssemblyResult(
            parsing=parsing,
            source_rankings=source_rankings,
            selected_sources=selected_sources,
            dataset_shape=assembly_info["shape"],
            columns=assembly_info["columns"],
            provenance=assembly_info["provenance"],
            warnings=assembly_info.get("warnings"),
            synthetic_recommendation=synthetic_rec
        )

    async def _parse_query(self, question: str) -> QueryParsing:
        """
        Parse natural language research question using AI or rule-based approach.
        """
        logger.info("Parsing research query")

        # Try AI-powered parsing first if available
        if settings.has_ai_provider:
            try:
                return await self._ai_parse_query(question)
            except Exception as e:
                logger.warning(f"AI parsing failed, falling back to rule-based: {e}")

        # Fall back to rule-based parsing
        return self._rule_based_parse(question)

    async def _ai_parse_query(self, question: str) -> QueryParsing:
        """Parse query using AI (OpenAI or Anthropic)."""
        import openai
        import anthropic

        prompt = f"""
        Parse this medical research question and extract the key components:

        Question: "{question}"

        Please identify:
        1. Outcomes (dependent variables)
        2. Exposures (primary independent variables of interest)
        3. Confounders (variables to control for)
        4. Cohort bounds (age, sex, time restrictions)
        5. Required variables (all variables needed for analysis)

        Respond with JSON in this format:
        {{
            "outcomes": ["outcome1", "outcome2"],
            "exposures": ["exposure1", "exposure2"],
            "confounders": ["confounder1", "confounder2"],
            "cohort_bounds": {{"age_range": [min, max], "sex": ["male", "female"], "time_period": "YYYY-YYYY"}},
            "required_variables": ["var1", "var2", "var3"],
            "research_area": "cardiovascular_risk|diabetes|cancer|inflammation|other",
            "confidence": 0.85
        }}

        Use common medical terminology. Map terms like:
        - "CRP" or "C-reactive protein" → "crp"
        - "BMI" → "bmi"
        - "blood pressure" → "systolic_bp", "diastolic_bp"
        - "age" → "age"
        - "sex" or "gender" → "sex"
        """

        try:
            if settings.openai_api_key:
                client = openai.OpenAI(api_key=settings.openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a medical research expert who parses research questions."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1
                )
                content = response.choices[0].message.content
            elif settings.anthropic_api_key:
                client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                response = client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content = response.content[0].text
            else:
                raise ValueError("No AI provider configured")

            # Extract JSON from response
            json_match = re.search(r'\\{.*\\}', content, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group())
                return QueryParsing(**parsed_data)
            else:
                raise ValueError("Could not extract JSON from AI response")

        except Exception as e:
            logger.error(f"AI query parsing failed: {e}")
            raise

    def _rule_based_parse(self, question: str) -> QueryParsing:
        """Parse query using rule-based approach."""
        logger.info("Using rule-based query parsing")

        question_lower = question.lower()

        # Extract outcomes using common patterns
        outcomes = []
        outcome_patterns = [
            r"predict\\s+(\\w+(?:\\s+\\w+)*)",
            r"risk\\s+of\\s+(\\w+(?:\\s+\\w+)*)",
            r"development\\s+of\\s+(\\w+(?:\\s+\\w+)*)",
            r"associated\\s+with\\s+(\\w+(?:\\s+\\w+)*)",
        ]

        for pattern in outcome_patterns:
            matches = re.findall(pattern, question_lower)
            for match in matches:
                outcomes.extend(self._normalize_terms([match]))

        # Extract exposures
        exposures = []
        exposure_patterns = [
            r"does\\s+(\\w+(?:\\s+\\w+)*)",
            r"effect\\s+of\\s+(\\w+(?:\\s+\\w+)*)",
            r"elevated\\s+(\\w+)",
            r"(crp|c-reactive protein|bmi|body mass index|cholesterol|glucose)",
        ]

        for pattern in exposure_patterns:
            matches = re.findall(pattern, question_lower)
            for match in matches:
                exposures.extend(self._normalize_terms([match]))

        # Extract age ranges
        age_range = None
        age_match = re.search(r"(\\d+)[–-](\\d+)", question)
        if age_match:
            age_range = [int(age_match.group(1)), int(age_match.group(2))]
        elif re.search(r"adult", question_lower):
            age_range = [18, 80]

        # Extract sex
        sex = []
        if re.search(r"\\bmen\\b|\\bmale\\b", question_lower):
            sex.append("male")
        if re.search(r"\\bwomen\\b|\\bfemale\\b", question_lower):
            sex.append("female")
        if not sex:
            sex = ["male", "female"]

        # Common confounders based on research area
        confounders = ["age", "sex", "race_ethnicity", "bmi"]

        # Determine research area
        research_area = "other"
        if any(term in question_lower for term in ["cardiovascular", "heart", "cardiac", "cvd"]):
            research_area = "cardiovascular_risk"
        elif any(term in question_lower for term in ["diabetes", "glucose", "insulin"]):
            research_area = "diabetes_research"
        elif any(term in question_lower for term in ["inflammation", "crp", "inflammatory"]):
            research_area = "inflammation"
        elif any(term in question_lower for term in ["cancer", "tumor", "oncology"]):
            research_area = "cancer"

        # Combine all required variables
        required_variables = list(set(outcomes + exposures + confounders))

        return QueryParsing(
            outcomes=outcomes or ["outcome"],
            exposures=exposures or ["exposure"],
            confounders=confounders,
            cohort_bounds={
                "age_range": age_range,
                "sex": sex,
            },
            required_variables=required_variables,
            research_area=research_area,
            confidence=0.7  # Lower confidence for rule-based parsing
        )

    def _normalize_terms(self, terms: List[str]) -> List[str]:
        """Normalize medical terms to standard variable names."""
        normalized = []
        term_mapping = {
            "c-reactive protein": "crp",
            "c reactive protein": "crp",
            "body mass index": "bmi",
            "blood pressure": "systolic_bp",
            "systolic blood pressure": "systolic_bp",
            "diastolic blood pressure": "diastolic_bp",
            "cardiovascular": "cardiovascular_events",
            "heart disease": "heart_disease",
            "diabetes": "diabetes",
            "gender": "sex",
        }

        for term in terms:
            term_clean = term.strip().lower()
            normalized_term = term_mapping.get(term_clean, term_clean.replace(" ", "_"))
            normalized.append(normalized_term)

        return normalized

    async def _rank_sources(
        self, parsing: QueryParsing, constraints: Optional[ResearchConstraints]
    ) -> List[DataSourceRanking]:
        """Rank available data sources based on query requirements."""
        logger.info("Ranking data sources")

        rankings = []

        # Rank NHANES
        nhanes_ranking = await self._rank_nhanes(parsing, constraints)
        if nhanes_ranking:
            rankings.append(nhanes_ranking)

        # Rank SEER (for cancer research)
        if parsing.research_area == "cancer" or any("cancer" in outcome for outcome in parsing.outcomes):
            seer_ranking = await self._rank_seer(parsing, constraints)
            if seer_ranking:
                rankings.append(seer_ranking)

        # Rank PhysioNet (for physiological signals)
        if any(term in parsing.research_area for term in ["ecg", "eeg", "physiological"]):
            physionet_ranking = await self._rank_physionet(parsing, constraints)
            if physionet_ranking:
                rankings.append(physionet_ranking)

        # Sort by score
        rankings.sort(key=lambda x: x.score, reverse=True)

        return rankings

    async def _rank_nhanes(
        self, parsing: QueryParsing, constraints: Optional[ResearchConstraints]
    ) -> Optional[DataSourceRanking]:
        """Rank NHANES as a data source."""
        try:
            # Check variable coverage
            available_vars = self._get_nhanes_variables()
            required_vars = parsing.required_variables

            covered_vars = [var for var in required_vars if self._find_nhanes_variable(var)]
            missing_vars = [var for var in required_vars if not self._find_nhanes_variable(var)]

            variable_coverage = len(covered_vars) / len(required_vars) if required_vars else 0

            # Estimate sample size
            if self.mcp_client:
                result = await self.mcp_client.nhanes_get(
                    cycles=constraints.cycles if constraints else None,
                    columns=["SEQN"],
                    where=self._build_nhanes_filters(constraints) if constraints else {},
                    dry_run=True
                )
                estimated_rows = result.estimated_rows or 0
            else:
                estimated_rows = 10000  # Default estimate

            # Calculate scoring components
            schema_fit = 0.9 if parsing.research_area in ["cardiovascular_risk", "diabetes_research", "inflammation"] else 0.6
            license_fit = 1.0  # NHANES is public domain
            recency = 0.8  # Recent cycles available

            # Overall score
            score = (variable_coverage * 0.4 + schema_fit * 0.3 + license_fit * 0.2 + recency * 0.1)

            return DataSourceRanking(
                source=DataSource.NHANES,
                score=score,
                variable_coverage=variable_coverage,
                schema_fit=schema_fit,
                license_fit=license_fit,
                recency=recency,
                estimated_rows=estimated_rows,
                required_variables=required_vars,
                available_variables=covered_vars,
                missing_variables=missing_vars
            )

        except Exception as e:
            logger.error(f"Error ranking NHANES: {e}")
            return None

    async def _rank_seer(
        self, parsing: QueryParsing, constraints: Optional[ResearchConstraints]
    ) -> Optional[DataSourceRanking]:
        """Rank SEER as a data source."""
        try:
            # SEER is good for cancer outcomes
            cancer_terms = ["cancer", "tumor", "oncology", "malignancy", "carcinoma"]
            has_cancer_outcome = any(
                any(term in outcome.lower() for term in cancer_terms)
                for outcome in parsing.outcomes
            )

            if not has_cancer_outcome:
                return None

            # Basic coverage for cancer research
            variable_coverage = 0.7
            schema_fit = 0.9 if has_cancer_outcome else 0.3
            license_fit = 1.0  # Public domain
            recency = 0.7

            estimated_rows = 50000  # Typical SEER query size

            score = (variable_coverage * 0.4 + schema_fit * 0.3 + license_fit * 0.2 + recency * 0.1)

            return DataSourceRanking(
                source=DataSource.SEER,
                score=score,
                variable_coverage=variable_coverage,
                schema_fit=schema_fit,
                license_fit=license_fit,
                recency=recency,
                estimated_rows=estimated_rows,
                required_variables=parsing.required_variables,
                available_variables=["site", "stage", "grade", "age_group", "sex", "race"],
                missing_variables=[]
            )

        except Exception as e:
            logger.error(f"Error ranking SEER: {e}")
            return None

    async def _rank_physionet(
        self, parsing: QueryParsing, constraints: Optional[ResearchConstraints]
    ) -> Optional[DataSourceRanking]:
        """Rank PhysioNet as a data source."""
        try:
            # PhysioNet is good for physiological signals
            signal_terms = ["ecg", "eeg", "emg", "signal", "waveform", "physiological"]
            has_signal_data = any(
                any(term in var.lower() for term in signal_terms)
                for var in parsing.required_variables
            )

            if not has_signal_data:
                return None

            variable_coverage = 0.6
            schema_fit = 0.8 if has_signal_data else 0.2
            license_fit = 0.9  # Mostly open licenses
            recency = 0.6

            estimated_rows = 100000  # Signal data can be large

            score = (variable_coverage * 0.4 + schema_fit * 0.3 + license_fit * 0.2 + recency * 0.1)

            return DataSourceRanking(
                source=DataSource.PHYSIONET,
                score=score,
                variable_coverage=variable_coverage,
                schema_fit=schema_fit,
                license_fit=license_fit,
                recency=recency,
                estimated_rows=estimated_rows,
                required_variables=parsing.required_variables,
                available_variables=["time", "signal", "annotation"],
                missing_variables=[]
            )

        except Exception as e:
            logger.error(f"Error ranking PhysioNet: {e}")
            return None

    def _select_sources(
        self, rankings: List[DataSourceRanking], preferred: Optional[List[DataSource]]
    ) -> List[DataSource]:
        """Select optimal data sources based on rankings and preferences."""
        if not rankings:
            return []

        # If user has preferences, prioritize them
        if preferred:
            available_preferred = [
                source for source in preferred
                if any(r.source == source for r in rankings)
            ]
            if available_preferred:
                return available_preferred[:2]  # Limit to top 2

        # Otherwise, select top-ranked sources
        selected = []
        for ranking in rankings:
            if ranking.score > 0.5:  # Minimum threshold
                selected.append(ranking.source)
                if len(selected) >= 2:  # Limit to top 2 sources
                    break

        return selected or [rankings[0].source]  # At least select the best one

    async def _assemble_dataset(
        self, parsing: QueryParsing, sources: List[DataSource], constraints: Optional[ResearchConstraints]
    ) -> Dict[str, Any]:
        """Assemble dataset from selected sources."""
        logger.info(f"Assembling dataset from sources: {sources}")

        all_data = []
        all_columns = set()
        provenance = []
        warnings = []

        # Fetch data from each source
        for source in sources:
            try:
                if source == DataSource.NHANES:
                    data, prov = await self._fetch_nhanes_data(parsing, constraints)
                elif source == DataSource.SEER:
                    data, prov = await self._fetch_seer_data(parsing, constraints)
                elif source == DataSource.PHYSIONET:
                    data, prov = await self._fetch_physionet_data(parsing, constraints)
                else:
                    continue

                if data:
                    all_data.extend(data)
                    all_columns.update(data[0].keys() if data else [])
                    provenance.append(prov)

            except Exception as e:
                logger.error(f"Error fetching data from {source}: {e}")
                warnings.append(f"Failed to fetch data from {source.value}: {str(e)}")

        # Calculate final shape
        total_rows = len(all_data)
        total_cols = len(all_columns)

        return {
            "shape": [total_rows, total_cols],
            "columns": list(all_columns),
            "data": all_data,
            "provenance": provenance,
            "warnings": warnings if warnings else None
        }

    async def _fetch_nhanes_data(
        self, parsing: QueryParsing, constraints: Optional[ResearchConstraints]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Fetch data from NHANES."""
        if not self.mcp_client:
            raise ValueError("MCP client not initialized")

        # Map variables to NHANES codes
        nhanes_columns = []
        for var in parsing.required_variables:
            nhanes_var = self._find_nhanes_variable(var)
            if nhanes_var:
                nhanes_columns.append(nhanes_var)

        # Always include SEQN for merging
        if "SEQN" not in nhanes_columns:
            nhanes_columns.insert(0, "SEQN")

        # Build filters
        filters = self._build_nhanes_filters(constraints) if constraints else {}

        # Fetch data
        result = await self.mcp_client.nhanes_get(
            cycles=constraints.cycles if constraints else None,
            columns=nhanes_columns,
            where=filters,
            limit=constraints.sample_size_max if constraints else 10000
        )

        return result.data or [], result.provenance.dict()

    async def _fetch_seer_data(
        self, parsing: QueryParsing, constraints: Optional[ResearchConstraints]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Fetch data from SEER."""
        if not self.mcp_client:
            raise ValueError("MCP client not initialized")

        # Determine appropriate SEER endpoint
        endpoint = "incidence"  # Default to incidence data

        # Build parameters
        params = {}
        if constraints and constraints.age_range:
            if constraints.age_range[0] < 20:
                params["age_group"] = "0-19"
            elif constraints.age_range[1] < 50:
                params["age_group"] = "20-49"
            elif constraints.age_range[1] < 65:
                params["age_group"] = "50-64"
            else:
                params["age_group"] = "65+"

        # Fetch data
        result = await self.mcp_client.seer_query(
            endpoint=endpoint,
            params=params,
            limit=constraints.sample_size_max if constraints else 5000
        )

        return result.data or [], result.provenance.dict()

    async def _fetch_physionet_data(
        self, parsing: QueryParsing, constraints: Optional[ResearchConstraints]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Fetch data from PhysioNet."""
        if not self.mcp_client:
            raise ValueError("MCP client not initialized")

        # Search for relevant datasets first
        catalog_result = await self.mcp_client.physionet_catalog(
            query="ECG",  # Default search
            category="ecg",
            limit=5
        )

        if not catalog_result.datasets:
            return [], {}

        # Use first available dataset
        dataset = catalog_result.datasets[0]

        # Fetch sample data
        result = await self.mcp_client.physionet_fetch(
            dataset=dataset.id,
            limit=constraints.sample_size_max if constraints else 1000
        )

        return result.data or [], result.provenance.dict()

    def _get_nhanes_variables(self) -> List[str]:
        """Get list of available NHANES variables."""
        if not self._nhanes_dict:
            return []

        variables = []
        for category in self._nhanes_dict.get("categories", {}).values():
            for var_data in category.get("variables", {}).values():
                variables.append(var_data.get("nhanes_code", ""))

        return [var for var in variables if var]

    def _find_nhanes_variable(self, search_term: str) -> Optional[str]:
        """Find NHANES variable code for a search term."""
        if not self._nhanes_dict:
            return None

        search_lower = search_term.lower().replace("_", " ")

        # Search through all categories
        for category in self._nhanes_dict.get("categories", {}).values():
            for var_name, var_data in category.get("variables", {}).items():
                # Check direct name match
                if var_name.lower() == search_term.lower():
                    return var_data.get("nhanes_code")

                # Check aliases
                aliases = var_data.get("aliases", [])
                if any(alias.lower() == search_term.lower() for alias in aliases):
                    return var_data.get("nhanes_code")

                # Check label match
                label = var_data.get("label", "").lower()
                if search_lower in label:
                    return var_data.get("nhanes_code")

        return None

    def _build_nhanes_filters(self, constraints: ResearchConstraints) -> Dict[str, Any]:
        """Build NHANES filter conditions from constraints."""
        filters = {}

        if constraints.age_range:
            filters["RIDAGEYR"] = constraints.age_range

        if constraints.sex:
            sex_codes = []
            for sex in constraints.sex:
                if sex.lower() == "male":
                    sex_codes.append(1)
                elif sex.lower() == "female":
                    sex_codes.append(2)
            if sex_codes:
                filters["RIAGENDR"] = sex_codes

        return filters

    def _evaluate_synthetic_need(
        self, assembly_info: Dict[str, Any], parsing: QueryParsing
    ) -> Optional[Dict[str, Any]]:
        """Evaluate if synthetic data generation is recommended."""
        total_rows = assembly_info["shape"][0]

        # Recommend synthetic data if sample size is small
        if total_rows < 1000:
            return {
                "recommended": True,
                "reason": "Small sample size",
                "suggested_size": 10000,
                "method": "ctgan"
            }

        # Check for class imbalance (simplified)
        if total_rows < 5000:
            return {
                "recommended": True,
                "reason": "Moderate sample size, could benefit from augmentation",
                "suggested_size": 20000,
                "method": "vae"
            }

        return None