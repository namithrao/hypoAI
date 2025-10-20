"""
Data models for multi-agent system.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ResearchPlan(BaseModel):
    """Structured research plan extracted from hypothesis."""

    hypothesis: str = Field(..., description="Original hypothesis text")
    outcome: str = Field(..., description="Primary outcome/dependent variable")
    exposures: List[str] = Field(..., description="Primary exposures/independent variables")
    confounders: Optional[List[str]] = Field(default=None, description="Potential confounding variables")
    population: Dict[str, Any] = Field(
        default_factory=dict,
        description="Target population criteria (age, sex, conditions, etc.)"
    )
    time_horizon: Optional[str] = Field(None, description="Time period for outcome (e.g., '1-year', '5-year')")
    study_design: Optional[str] = Field(None, description="Suggested study design (cohort, case-control, etc.)")
    data_gaps: Optional[List[str]] = Field(default=None, description="Anticipated data gaps or limitations")


class VariableMapping(BaseModel):
    """Mapping of conceptual variable to NHANES implementation."""

    concept: str = Field(..., description="Conceptual variable name from literature")
    nhanes_variable: Optional[str] = Field(None, description="NHANES variable code (discovered dynamically)")
    nhanes_description: Optional[str] = Field(None, description="NHANES variable description")
    data_category: Optional[str] = Field(None, description="NHANES data category")
    file_name: Optional[str] = Field(None, description="NHANES data file description")
    transformation: Optional[str] = Field(None, description="Required transformation (e.g., 'log', 'categorize')")
    cutoff: Optional[float] = Field(None, description="Clinical cutoff value from literature")
    unit: Optional[str] = Field(None, description="Unit of measurement")


class EvidenceSpec(BaseModel):
    """Evidence extracted from literature review."""

    research_plan: ResearchPlan
    papers_reviewed: int = Field(..., description="Number of papers reviewed")
    top_papers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top relevant papers with metadata"
    )
    variable_mappings: List[VariableMapping] = Field(
        default_factory=list,
        description="Variable mappings extracted from literature"
    )
    effect_sizes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Reported effect sizes from literature"
    )
    recommended_covariates: List[str] = Field(
        default_factory=list,
        description="Covariates recommended by literature"
    )
    mesh_terms: List[str] = Field(
        default_factory=list,
        description="Relevant MeSH terms discovered"
    )


class DataFileSpec(BaseModel):
    """Specification for a single NHANES data file."""

    data_category: str = Field(..., description="NHANES data category")
    file_name: str = Field(..., description="Data file description")
    cycle_mapping: Dict[str, str] = Field(
        ...,
        description="Mapping of cycle years to actual file names"
    )
    variables: List[str] = Field(..., description="Variables to extract from this file")
    common_variables: List[str] = Field(
        default_factory=list,
        description="Variables common across all requested cycles"
    )
    uncommon_variables: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Variables not in all cycles: {var: [cycles_present]}"
    )


class DataAssemblySpec(BaseModel):
    """Complete specification for NHANES data assembly."""

    evidence_spec: EvidenceSpec
    cycles: List[str] = Field(..., description="Selected NHANES cycles")
    data_files: List[DataFileSpec] = Field(..., description="Data files to retrieve")
    join_strategy: str = Field(default="inner", description="Join strategy (inner, outer)")
    variable_harmonization: Dict[str, Any] = Field(
        default_factory=dict,
        description="Harmonization rules for variables across cycles"
    )


class SyntheticDataConfig(BaseModel):
    """Configuration for synthetic data generation."""

    method: str = Field(default="umap_vae", description="Generation method")
    sample_size: int = Field(..., description="Number of synthetic samples to generate")
    umap_params: Dict[str, Any] = Field(
        default_factory=lambda: {"n_neighbors": 15, "min_dist": 0.1, "n_components": 10}
    )
    vae_params: Dict[str, Any] = Field(
        default_factory=lambda: {"latent_dim": 10, "epochs": 100, "batch_size": 32}
    )
    preserve_correlations: bool = Field(default=True)
    preserve_distributions: bool = Field(default=True)


class AnalysisResult(BaseModel):
    """Results from statistical analysis."""

    model_type: str = Field(..., description="Type of model used")
    coefficients: Dict[str, float] = Field(default_factory=dict)
    p_values: Dict[str, float] = Field(default_factory=dict)
    confidence_intervals: Dict[str, List[float]] = Field(default_factory=dict)
    metrics: Dict[str, float] = Field(default_factory=dict, description="Model performance metrics")
    shap_values: Optional[Dict[str, Any]] = Field(None, description="SHAP explanations")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Model diagnostics")
