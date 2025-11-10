"""
Literature Discovery Agent for SynthAI MVP.

Simplified single-agent architecture:
- Literature Discovery Agent V2: Claude + BlueBERT for variable discovery from research papers

Legacy agents (commented out for MVP):
- Research Planner, Literature Review, Data Sourcing, Dataset Builder (to be removed)
"""

# MVP Implementation
from .literature_discovery_agent_v2 import LiteratureDiscoveryAgentV2

# Legacy agents (commented out)
# from .research_planner import ResearchPlannerAgent
# from .literature_review import LiteratureReviewAgent
# from .data_sourcing import DataSourcingAgent
# from .dataset_builder import DatasetBuilderAgent

__all__ = [
    "LiteratureDiscoveryAgentV2",
]
