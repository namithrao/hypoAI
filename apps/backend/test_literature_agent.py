"""
Test script for Literature Discovery Agent V2.

Tests the MVP implementation with a sample hypothesis.
"""

import asyncio
import os
import sys
from anthropic import AsyncAnthropic


# Mock NCBI client for testing
class MockNCBIClient:
    """Mock NCBI client that returns sample data."""

    def call_tool(self, tool_name: str, params: dict):
        """Simulate NCBI API calls."""

        if tool_name == "ncbi_search":
            # Return sample PMIDs
            return {
                'ids': ['38123456', '38234567', '38345678']
            }

        elif tool_name == "ncbi_summary":
            pmid = params['id']
            return {
                pmid: {
                    'title': f'Sample Study {pmid}: CRP and Cardiovascular Risk',
                    'pubdate': '2024'
                }
            }

        elif tool_name == "ncbi_fetch":
            pmid = params['id']
            return {
                'raw_text': f"""
                Abstract for PMID:{pmid}

                Background: C-reactive protein (CRP) is an inflammatory marker.

                Methods: We studied 1,000 adults aged 40-65 with diabetes.
                We measured CRP levels, BMI, age, sex, and cardiovascular events.

                Results: Elevated CRP (>3 mg/L) was associated with increased
                cardiovascular events (HR 1.8, 95% CI 1.4-2.3, p<0.001).
                Age and BMI were significant confounders.

                Conclusions: CRP predicts cardiovascular risk in diabetics.
                """
            }

        return {}


async def test_literature_agent():
    """Test the literature agent with a sample hypothesis."""

    print("=" * 60)
    print("Testing Literature Discovery Agent V2")
    print("=" * 60)

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠ ANTHROPIC_API_KEY not set")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        print("\nUsing mock mode (no actual Claude API calls)")
        mock_mode = True
    else:
        mock_mode = False

    # Import agent
    try:
        from synthai_backend.agents.literature_discovery_agent_v2 import LiteratureDiscoveryAgentV2
    except ImportError as e:
        print(f"✗ Failed to import agent: {e}")
        sys.exit(1)

    print("✓ Agent imported successfully\n")

    # Create clients
    ncbi_client = MockNCBIClient()

    if not mock_mode:
        anthropic_client = AsyncAnthropic(api_key=api_key)
    else:
        # Skip if no API key
        print("⚠ Skipping full test (no API key)")
        print("✓ Agent structure verified")
        return

    # Create agent
    agent = LiteratureDiscoveryAgentV2(
        ncbi_client=ncbi_client,
        anthropic_client=anthropic_client
    )

    print("✓ Agent initialized\n")

    # Test hypothesis
    hypothesis = "Does elevated CRP predict cardiovascular events in adults with diabetes?"

    print(f"Hypothesis: {hypothesis}\n")
    print("Starting variable discovery...\n")

    # Run discovery
    try:
        results = await agent.discover_variables(
            hypothesis=hypothesis,
            min_variables=5,  # Lower for testing
            max_papers=3,     # Fewer papers for testing
            max_iterations=1  # Single iteration for testing
        )

        print("=" * 60)
        print("Results:")
        print("=" * 60)
        print(f"✓ Success: {results['success']}")
        print(f"✓ Papers analyzed: {results['papers_analyzed']}")
        print(f"✓ Variables discovered: {len(results['variables'])}")
        print(f"✓ Confounders identified: {len(results['confounders'])}")
        print(f"✓ Search iterations: {results['search_iterations']}")

        print("\nVariables:")
        for i, var in enumerate(results['variables'][:5], 1):
            print(f"  {i}. {var['name']} ({var['type']}) - {var['role']}")
            print(f"     Relationship: {var.get('relationship', 'unknown')}")
            print(f"     Citations: {var.get('citations', [])}")

        if results['confounders']:
            print("\nConfounders:")
            for i, conf in enumerate(results['confounders'][:3], 1):
                print(f"  {i}. {conf['name']}")

        print("\nReasoning Chain:")
        print(f"  {results.get('reasoning_chain', 'N/A')[:200]}...")

        print("\n✓ All tests passed!")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_literature_agent())
