"""
Multi-agent medical research system.

Agents:
1. Research Planner - Parses hypotheses into structured research plans
2. Literature Review - Searches PubMed/OpenAlex for evidence
3. Data Sourcing - Discovers NHANES variables dynamically
4. Dataset Builder - Harmonizes and joins multi-cycle data
5. Synthetic Data Engine - Augments data with UMAP+VAE
6. Statistical Analysis - Runs models and generates explanations
7. Report Generation - Creates publication-ready outputs
"""

from .research_planner import ResearchPlannerAgent
from .literature_review import LiteratureReviewAgent
from .data_sourcing import DataSourcingAgent
from .dataset_builder import DatasetBuilderAgent

__all__ = [
    "ResearchPlannerAgent",
    "LiteratureReviewAgent",
    "DataSourcingAgent",
    "DatasetBuilderAgent",
]
