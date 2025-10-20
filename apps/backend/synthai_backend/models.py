"""
Pydantic models for API requests and responses.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, UUID4


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataSource(str, Enum):
    """Available data sources."""
    NHANES = "nhanes"
    SEER = "seer"
    PHYSIONET = "physionet"
    USER_UPLOAD = "user_upload"


class SynthMethod(str, Enum):
    """Synthetic data generation methods."""
    CTGAN = "ctgan"
    COPULAS = "copulas"
    VAE = "vae"
    UMAP_VAE = "umap_vae"
    GRETEL = "gretel"


class AnalysisModel(str, Enum):
    """Statistical analysis models."""
    LOGISTIC = "logistic"
    LINEAR = "linear"
    SURVIVAL = "survival"
    BAYESIAN = "bayesian"
    GRADIENT_BOOSTING = "gradient_boosting"


# Base Models
class BaseResponse(BaseModel):
    """Base response model."""
    success: bool = True
    message: str = "Success"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    """Error response model."""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(default_factory=dict)


# Research Query Models
class ResearchConstraints(BaseModel):
    """Constraints for research queries."""
    age_range: Optional[List[int]] = Field(None, min_items=2, max_items=2)
    sex: Optional[List[str]] = None
    race_ethnicity: Optional[List[str]] = None
    cycles: Optional[List[str]] = None
    sample_size_min: Optional[int] = None
    sample_size_max: Optional[int] = None
    exclude_missing_outcome: bool = True


class ResearchQuery(BaseModel):
    """Research question query."""
    question: str = Field(..., min_length=10, max_length=1000)
    user_data: Optional[str] = None  # Base64 encoded CSV
    constraints: Optional[ResearchConstraints] = None
    preferred_sources: Optional[List[DataSource]] = None


class DataSourceRanking(BaseModel):
    """Data source ranking information."""
    source: DataSource
    score: float = Field(..., ge=0, le=1)
    variable_coverage: float = Field(..., ge=0, le=1)
    schema_fit: float = Field(..., ge=0, le=1)
    license_fit: float = Field(..., ge=0, le=1)
    recency: float = Field(..., ge=0, le=1)
    estimated_rows: int
    required_variables: List[str]
    available_variables: List[str]
    missing_variables: List[str]


class QueryParsing(BaseModel):
    """Parsed research query components."""
    outcomes: List[str]
    exposures: List[str]
    confounders: List[str]
    cohort_bounds: Dict[str, Any]
    required_variables: List[str]
    research_area: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)


class AssemblyResult(BaseModel):
    """Data assembly result."""
    query_id: UUID4 = Field(default_factory=uuid.uuid4)
    parsing: QueryParsing
    source_rankings: List[DataSourceRanking]
    selected_sources: List[DataSource]
    dataset_shape: List[int]  # [rows, columns]
    columns: List[str]
    provenance: List[Dict[str, Any]]
    warnings: Optional[List[str]] = None
    synthetic_recommendation: Optional[Dict[str, Any]] = None


# Synthetic Data Models
class SynthConfig(BaseModel):
    """Synthetic data generation configuration."""
    method: SynthMethod = SynthMethod.CTGAN
    sample_size: int = Field(..., gt=0, le=1000000)
    noise: float = Field(default=0.05, ge=0, le=1)
    distributions: Optional[Dict[str, str]] = None
    correlations: Optional[List[Dict[str, Union[str, float]]]] = None
    random_seed: int = Field(default=42, ge=0)
    dp_epsilon: Optional[float] = Field(None, gt=0, le=10)

    # Advanced options
    epochs: Optional[int] = Field(default=300, gt=0)
    batch_size: Optional[int] = Field(default=500, gt=0)
    learning_rate: Optional[float] = Field(default=2e-4, gt=0)


class SynthResult(BaseModel):
    """Synthetic data generation result."""
    config: SynthConfig
    original_shape: List[int]
    synthetic_shape: List[int]
    generation_time: float
    quality_metrics: Dict[str, float]
    provenance: Dict[str, Any]
    warnings: Optional[List[str]] = None


# Analysis Models
class AnalysisConfig(BaseModel):
    """Statistical analysis configuration."""
    outcome: str
    exposures: List[str]
    confounders: Optional[List[str]] = None
    models: List[AnalysisModel] = [AnalysisModel.LOGISTIC]
    train_test_split: float = Field(default=0.8, gt=0, lt=1)
    cross_validation_folds: int = Field(default=5, ge=2)
    random_seed: int = Field(default=42, ge=0)

    # Model-specific options
    survival_time_col: Optional[str] = None
    survival_event_col: Optional[str] = None
    bayesian_samples: int = Field(default=2000, gt=0)
    shap_sample_size: int = Field(default=1000, gt=0)


class ModelResult(BaseModel):
    """Individual model result."""
    model_type: AnalysisModel
    coefficients: Dict[str, float]
    p_values: Optional[Dict[str, float]] = None
    confidence_intervals: Optional[Dict[str, List[float]]] = None
    metrics: Dict[str, float]
    feature_importance: Optional[Dict[str, float]] = None


class AnalysisResult(BaseModel):
    """Complete analysis result."""
    config: AnalysisConfig
    data_summary: Dict[str, Any]
    model_results: List[ModelResult]
    shap_values: Optional[Dict[str, Any]] = None
    plots: Dict[str, str]  # Plot names to base64 encoded images
    interpretation: str
    limitations: List[str]
    next_steps: List[str]


# Report Models
class ReportConfig(BaseModel):
    """Report generation configuration."""
    title: str
    include_methods: bool = True
    include_data_summary: bool = True
    include_results: bool = True
    include_plots: bool = True
    include_interpretation: bool = True
    include_limitations: bool = True
    include_next_steps: bool = True
    format: str = Field(default="pdf", regex="^(html|pdf)$")


class ReportResult(BaseModel):
    """Generated report result."""
    report_id: UUID4 = Field(default_factory=uuid.uuid4)
    config: ReportConfig
    file_path: str
    file_size: int
    generation_time: float
    download_url: str


# Task Management Models
class TaskInfo(BaseModel):
    """Task information."""
    task_id: UUID4 = Field(default_factory=uuid.uuid4)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    progress: float = Field(default=0.0, ge=0, le=1)
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class TaskResponse(BaseResponse):
    """Task response with task information."""
    task: TaskInfo


# File Upload Models
class FileUpload(BaseModel):
    """File upload information."""
    filename: str
    size: int
    content_type: str
    columns: List[str]
    rows: int
    preview: List[Dict[str, Any]]  # First few rows


class UploadResponse(BaseResponse):
    """File upload response."""
    file: FileUpload
    upload_id: UUID4 = Field(default_factory=uuid.uuid4)


# Data Preview Models
class DataPreview(BaseModel):
    """Data preview with metadata."""
    shape: List[int]  # [rows, columns]
    columns: List[str]
    dtypes: Dict[str, str]
    sample_data: List[Dict[str, Any]]
    summary_stats: Optional[Dict[str, Any]] = None
    missing_values: Dict[str, int]
    provenance: List[Dict[str, Any]]


# Run History Models
class RunHistory(BaseModel):
    """Research run history."""
    run_id: UUID4 = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    query: str
    config: Dict[str, Any]
    status: TaskStatus
    results_available: bool = False


class RunHistoryResponse(BaseResponse):
    """Run history response."""
    runs: List[RunHistory]
    total: int
    page: int
    page_size: int