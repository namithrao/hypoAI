"""
Test script for Literature Discovery Agent V2 with dual output system.
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import AsyncAnthropic
from synthai_backend.agents.literature_discovery_agent_v2 import LiteratureDiscoveryAgentV2

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)


async def test_literature_agent():
    """Test the literature discovery agent with a sample hypothesis."""

    # Get API keys from environment
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    ncbi_key = os.getenv("NCBI_API_KEY")

    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY not set in environment")
        return

    if ncbi_key:
        print(f"✅ NCBI API key found (enables 10 req/s)")
    else:
        print(f"⚠️  NCBI API key not found (limited to 3 req/s)")

    print("=" * 80)
    print("TESTING LITERATURE DISCOVERY AGENT V2")
    print("=" * 80)

    # Create agent
    anthropic_client = AsyncAnthropic(api_key=anthropic_key)
    agent = LiteratureDiscoveryAgentV2(
        ncbi_client=None,  # Not used, agent uses direct HTTP
        anthropic_client=anthropic_client,
        ncbi_api_key=ncbi_key
    )

    # Test hypothesis
    hypothesis = "Does elevated C-reactive protein predict cardiovascular events in adults with type 2 diabetes?"

    print(f"\n📋 Hypothesis: {hypothesis}")
    print(f"🎯 Target: Find 10 variables")
    print(f"📚 Max papers: 5 (for testing)")
    print(f"🔄 Max iterations: 2\n")

    try:
        # Run discovery
        synthesis_input, literature_display = await agent.discover_variables(
            hypothesis=hypothesis,
            min_variables=10,
            max_papers=5,  # Keep small for testing
            max_iterations=2
        )

        print("\n" + "=" * 80)
        print("✅ DISCOVERY COMPLETED SUCCESSFULLY")
        print("=" * 80)

        # Display synthesis_input results
        print("\n📊 SYNTHESIS INPUT (for generator):")
        print(f"   Variables found: {len(synthesis_input['variables'])}")
        print(f"   Correlations: {len(synthesis_input['correlations'])}")
        print(f"   Source: {synthesis_input['source']}")

        print("\n   Variables:")
        for i, var in enumerate(synthesis_input['variables'][:5], 1):  # Show first 5
            print(f"   {i}. {var['name']}")
            print(f"      Type: {var['type']}, Distribution: {var['distribution']}")
            if var.get('range'):
                r = var['range']
                print(f"      Range: {r.get('min')} - {r.get('max')}, Mean: {r.get('mean')}, SD: {r.get('sd')}")
            print(f"      Units: {var.get('units', 'N/A')}")

        if len(synthesis_input['variables']) > 5:
            print(f"   ... and {len(synthesis_input['variables']) - 5} more")

        # Display literature_display results
        print("\n📚 LITERATURE DISPLAY (for frontend):")
        print(f"   Papers analyzed: {literature_display['total_papers_analyzed']}")
        print(f"   Variables found: {literature_display['variables_found']}")
        print(f"   Confounders found: {literature_display['confounders_found']}")
        print(f"   Search iterations: {literature_display['search_iterations']}")

        print("\n   Papers:")
        for i, paper in enumerate(literature_display['papers'], 1):
            print(f"\n   {i}. {paper['title']}")
            print(f"      PMID: {paper['pmid']}")
            print(f"      Authors: {', '.join(paper['authors'][:3])}")
            print(f"      Journal: {paper['journal']} ({paper['year']})")
            print(f"      Relevance: {paper['relevance'].upper()}")
            print(f"      Variables extracted: {len(paper['variables_extracted'])}")
            if paper['variables_extracted']:
                print(f"        {', '.join(paper['variables_extracted'])}")

            # Show abstract sections
            abstract = paper['abstract']
            if abstract.get('background'):
                print(f"      Abstract (Background): {abstract['background'][:100]}...")

            # Show if full text is available
            if paper.get('full_text'):
                sections = [k for k, v in paper['full_text'].items() if v]
                print(f"      ✅ Full text available: {', '.join(sections)}")
            else:
                print(f"      ❌ Full text not available")

        print("\n   Synthesis:")
        print(f"      Confidence: {literature_display['synthesis']['confidence'].upper()}")
        print(f"      Key relationships: {len(literature_display['synthesis']['key_relationships'])}")
        print(f"      Novel insights: {len(literature_display['synthesis']['novel_insights'])}")

        if literature_display['synthesis']['key_relationships']:
            print("\n      Key Relationships:")
            for rel in literature_display['synthesis']['key_relationships'][:3]:
                print(f"        - {rel}")

        if literature_display['synthesis']['novel_insights']:
            print("\n      Novel Insights:")
            for insight in literature_display['synthesis']['novel_insights'][:3]:
                print(f"        - {insight}")

        print("\n" + "=" * 80)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_literature_agent())
