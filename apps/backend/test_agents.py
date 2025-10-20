#!/usr/bin/env python3
"""
Quick test script to verify agents are working.
Run this to test the multi-agent pipeline without the frontend.
"""

import asyncio
import json
from synthai_backend.agents import (
    ResearchPlannerAgent,
    LiteratureReviewAgent,
    DataSourcingAgent,
    DatasetBuilderAgent,
)


async def test_pipeline():
    """Test the complete agent pipeline."""

    # Test hypothesis
    hypothesis = "Does elevated CRP predict 1-year cardiovascular events in adults aged 40-65?"

    print("=" * 80)
    print("SynthAI Multi-Agent Pipeline Test")
    print("=" * 80)
    print(f"\nHypothesis: {hypothesis}\n")

    # Agent 1: Research Planner
    print("🧠 Agent 1: Research Planner")
    print("-" * 80)
    planner = ResearchPlannerAgent()
    research_plan = await planner.parse_hypothesis(hypothesis)

    print(f"✓ Outcome: {research_plan.outcome}")
    print(f"✓ Exposures: {research_plan.exposures}")
    print(f"✓ Confounders: {research_plan.confounders}")
    print(f"✓ Study Design: {research_plan.study_design}")
    print(f"✓ Population: {research_plan.population}")

    # Agent 2: Literature Review
    print("\n📚 Agent 2: Literature Review")
    print("-" * 80)
    lit_agent = LiteratureReviewAgent()
    evidence_spec = await lit_agent.search_literature(research_plan, max_papers=10, min_year=2015)

    print(f"✓ Papers reviewed: {evidence_spec.papers_reviewed}")
    print(f"✓ Variable mappings found: {len(evidence_spec.variable_mappings)}")
    print(f"✓ Recommended covariates: {evidence_spec.recommended_covariates}")

    if evidence_spec.variable_mappings:
        print("\nVariable Mappings:")
        for vm in evidence_spec.variable_mappings[:3]:  # Show first 3
            print(f"  - {vm.concept}: {vm.unit or 'N/A'} (cutoff: {vm.cutoff or 'N/A'})")

    # Agent 3: Data Sourcing
    print("\n💾 Agent 3: Data Sourcing")
    print("-" * 80)
    data_agent = DataSourcingAgent()
    assembly_spec = await data_agent.source_data(evidence_spec, cycles=["2017-2018"], min_cycle_year=2017)

    print(f"✓ Cycles selected: {assembly_spec.cycles}")
    print(f"✓ Data files identified: {len(assembly_spec.data_files)}")

    for file_spec in assembly_spec.data_files:
        print(f"  - {file_spec.data_category}/{file_spec.file_name}")
        print(f"    Variables: {', '.join(file_spec.variables)}")

    # Agent 4: Dataset Builder
    print("\n🏗️  Agent 4: Dataset Builder")
    print("-" * 80)
    builder = DatasetBuilderAgent()

    try:
        dataset = await builder.build_dataset(
            assembly_spec,
            population_filters=research_plan.population
        )

        print(f"✓ Dataset built successfully!")
        print(f"✓ Shape: {dataset.shape[0]} rows × {dataset.shape[1]} columns")
        print(f"✓ Columns: {', '.join(list(dataset.columns)[:10])}...")

        # Get summary
        summary = builder.get_variable_summary(dataset)
        print(f"\nVariable Summary (first 3):")
        for i, (col, stats) in enumerate(list(summary.items())[:3]):
            print(f"  {col}:")
            print(f"    - Type: {stats['dtype']}")
            print(f"    - Count: {stats['count']}")
            print(f"    - Missing: {stats['missing_pct']:.1f}%")

    except Exception as e:
        print(f"⚠️  Dataset building failed (this may be expected if NHANES data not available)")
        print(f"   Error: {e}")

    # Cleanup
    await lit_agent.close()

    print("\n" + "=" * 80)
    print("✨ Pipeline test complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_pipeline())
