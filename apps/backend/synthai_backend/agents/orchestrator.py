"""
Multi-Agent Orchestrator

Coordinates all SynthAI agents to answer complex research questions:
1. Literature Discovery Agent - finds relevant papers and hypotheses
2. Dataset Discovery Agent - finds government health datasets
3. Integration Agent - harmonizes variables across datasets (TODO)
4. Analysis Agent - performs statistical analysis (TODO)

Key features:
- Zero hardcoding - LLM decides which agents to invoke and in what order
- Shared context between agents
- Comprehensive logging of orchestration decisions
"""

import logging
import json
from typing import List, Dict, Optional, Any
from anthropic import AsyncAnthropic

from .literature_agent import LiteratureDiscoveryAgent
from .dataset_discovery_agent import DatasetDiscoveryAgent

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """
    Orchestrates multiple specialized agents to solve research questions.

    The orchestrator uses an LLM to:
    1. Decompose research question into sub-tasks
    2. Decide which agents to invoke
    3. Determine execution order and dependencies
    4. Synthesize results from multiple agents
    """

    def __init__(
        self,
        literature_agent: LiteratureDiscoveryAgent,
        dataset_agent: DatasetDiscoveryAgent,
        anthropic_client: AsyncAnthropic,
    ):
        """
        Args:
            literature_agent: Agent for literature discovery
            dataset_agent: Agent for dataset discovery
            anthropic_client: Anthropic API client for orchestration decisions
        """
        self.literature_agent = literature_agent
        self.dataset_agent = dataset_agent
        self.anthropic = anthropic_client
        self.model = "claude-3-7-sonnet-20250219"

        # Shared context across agents
        self.context: Dict[str, Any] = {
            'research_question': None,
            'literature_findings': None,
            'datasets_found': None,
            'variables_identified': [],
            'hypotheses': [],
        }

    def _log_decision(self, decision: str, reason: str, details: Optional[Dict] = None):
        """Log orchestration decision"""
        logger.info(f"[ORCHESTRATOR-DECISION] {decision}")
        logger.info(f"[ORCHESTRATOR-REASON] {reason}")
        if details:
            logger.info(f"[ORCHESTRATOR-DETAILS] {json.dumps(details, indent=2)}")

    def _log_phase(self, phase: str, description: str):
        """Log orchestration phase"""
        logger.info(f"[ORCHESTRATOR-PHASE] {phase}")
        logger.info(f"[ORCHESTRATOR-INFO] {description}")

    async def research(
        self,
        question: str,
        max_papers: int = 10,
        max_datasets: int = 20,
    ) -> Dict[str, Any]:
        """
        Answer a research question using multiple agents.

        Args:
            question: Research question (e.g., "Does CRP predict cardiovascular events in diabetics?")
            max_papers: Maximum papers for literature review
            max_datasets: Maximum datasets to discover

        Returns:
            {
                'success': True,
                'research_question': original question,
                'execution_plan': {
                    'phases': [...],
                    'agent_invocations': [...],
                },
                'literature_findings': {...},
                'datasets_discovered': {...},
                'integration_plan': {...},  # TODO
                'recommended_next_steps': [...],
            }
        """
        logger.info(f"[ORCHESTRATOR] Starting research: {question}")
        self.context['research_question'] = question

        # Phase 1: LLM creates execution plan
        execution_plan = await self._create_execution_plan(question)

        # Phase 2: Execute plan
        results = await self._execute_plan(execution_plan, max_papers, max_datasets)

        # Phase 3: Synthesize findings
        synthesis = await self._synthesize_results(question, results)

        return {
            'success': True,
            'research_question': question,
            'execution_plan': execution_plan,
            **results,
            'synthesis': synthesis,
        }

    async def _create_execution_plan(self, question: str) -> Dict[str, Any]:
        """
        Phase 1: LLM decides which agents to invoke and in what order.
        """
        self._log_phase("PLANNING", "Creating execution plan")

        planning_prompt = f"""You are orchestrating a multi-agent research system.

Research question: "{question}"

Available agents:
1. **Literature Discovery Agent**: Searches PubMed, analyzes papers, finds genes/proteins/variants, generates hypotheses
2. **Dataset Discovery Agent**: Searches government data portals (CKAN, SODA) for relevant datasets
3. **Integration Agent**: (Not yet implemented) Would harmonize variables across datasets
4. **Analysis Agent**: (Not yet implemented) Would perform statistical analysis

For this research question, create an execution plan:

1. Which agents should be invoked?
2. In what order?
3. What information should each agent provide to the next?
4. What are the dependencies between agents?

Return JSON:
{{
  "phases": [
    {{
      "phase_number": 1,
      "agent": "literature_discovery",
      "goal": "What this agent should accomplish",
      "reason": "Why this agent should run first/next",
      "inputs": {{}},
      "outputs_needed": ["What the next agent needs from this one"]
    }},
    {{
      "phase_number": 2,
      "agent": "dataset_discovery",
      "goal": "...",
      "reason": "...",
      "inputs": {{"variables_from_literature": "output from phase 1"}},
      "outputs_needed": [...]
    }}
  ],
  "expected_outcome": "What we expect to learn from this multi-agent research"
}}

Only include agents that will genuinely help answer the question."""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": planning_prompt}]
        )

        # Extract JSON from response
        response_text = response.content[0].text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            json_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
            json_text = json_text.replace('```json', '').replace('```', '').strip()
        else:
            json_text = response_text

        plan = json.loads(json_text)

        self._log_decision(
            f"Execution plan: {len(plan['phases'])} phases",
            "LLM determined optimal agent sequence",
            {
                "agents": [p['agent'] for p in plan['phases']],
                "expected_outcome": plan.get('expected_outcome')
            }
        )

        for phase in plan['phases']:
            self._log_decision(
                f"Phase {phase['phase_number']}: {phase['agent']}",
                phase['reason'],
                {"goal": phase['goal']}
            )

        return plan

    async def _execute_plan(
        self,
        plan: Dict[str, Any],
        max_papers: int,
        max_datasets: int,
    ) -> Dict[str, Any]:
        """
        Phase 2: Execute the plan by invoking agents.
        """
        self._log_phase("EXECUTION", f"Executing {len(plan['phases'])} phase plan")

        results = {}

        for phase in plan['phases']:
            phase_num = phase['phase_number']
            agent_name = phase['agent']
            goal = phase['goal']

            self._log_phase(f"PHASE {phase_num}", f"{agent_name}: {goal}")

            try:
                if agent_name == 'literature_discovery':
                    # Invoke literature agent
                    hypothesis = self.context['research_question']

                    lit_results = await self.literature_agent.analyze(
                        hypothesis=hypothesis,
                        max_papers=max_papers
                    )

                    # Store in context for next agents
                    self.context['literature_findings'] = lit_results
                    self.context['variables_identified'] = lit_results.get('all_variables', [])
                    self.context['hypotheses'] = lit_results.get('synthesis', {}).get('novel_hypotheses', [])

                    results['literature_findings'] = lit_results

                    self._log_decision(
                        "Literature discovery complete",
                        f"Analyzed {lit_results.get('papers_analyzed', 0)} papers",
                        {
                            "variables_found": len(self.context['variables_identified']),
                            "hypotheses_generated": len(self.context['hypotheses']),
                        }
                    )

                elif agent_name == 'dataset_discovery':
                    # Invoke dataset agent
                    hypothesis = self.context['research_question']
                    variables = self.context['variables_identified']

                    if not variables or len(variables) == 0:
                        logger.warning("[ORCHESTRATOR-WARNING] No variables from literature, using question directly")
                        variables = []

                    dataset_results = await self.dataset_agent.discover(
                        hypothesis=hypothesis,
                        variables_needed=variables,
                        max_datasets=max_datasets
                    )

                    # Store in context
                    self.context['datasets_found'] = dataset_results

                    results['datasets_discovered'] = dataset_results

                    self._log_decision(
                        "Dataset discovery complete",
                        f"Found {dataset_results.get('total_returned', 0)} relevant datasets",
                        {
                            "portals_searched": len(dataset_results.get('search_strategy', {}).get('portals', [])),
                            "top_dataset": dataset_results['datasets'][0]['name'] if dataset_results.get('datasets') else None,
                        }
                    )

                elif agent_name == 'integration':
                    logger.warning(f"[ORCHESTRATOR-WARNING] Integration agent not yet implemented")
                    results['integration_plan'] = {"status": "not_implemented"}

                elif agent_name == 'analysis':
                    logger.warning(f"[ORCHESTRATOR-WARNING] Analysis agent not yet implemented")
                    results['analysis'] = {"status": "not_implemented"}

                else:
                    logger.warning(f"[ORCHESTRATOR-WARNING] Unknown agent: {agent_name}")

            except Exception as e:
                logger.error(f"[ORCHESTRATOR-ERROR] Phase {phase_num} failed: {str(e)}")
                results[f'phase_{phase_num}_error'] = str(e)

        return results

    async def _synthesize_results(
        self,
        question: str,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phase 3: LLM synthesizes findings from all agents.
        """
        self._log_phase("SYNTHESIS", "Synthesizing multi-agent findings")

        # Prepare summary of findings
        lit_findings = results.get('literature_findings', {})
        dataset_findings = results.get('datasets_discovered', {})

        synthesis_prompt = f"""You are synthesizing research findings from multiple AI agents.

Research question: "{question}"

**Literature Findings:**
- Papers analyzed: {lit_findings.get('papers_analyzed', 0)}
- Variables identified: {lit_findings.get('all_variables', [])}
- Genes found: {lit_findings.get('all_genes', [])}
- Novel hypotheses: {lit_findings.get('synthesis', {}).get('novel_hypotheses', [])}
- Research gaps: {lit_findings.get('synthesis', {}).get('research_gaps', [])}

**Dataset Findings:**
- Datasets found: {dataset_findings.get('total_found', 0)}
- Top datasets: {[d.get('name') for d in dataset_findings.get('datasets', [])[:5]]}
- Portals searched: {[p['name'] for p in dataset_findings.get('search_strategy', {}).get('portals', [])]}

Synthesize these findings:

1. **Answer**: Can we answer the research question with available data?
2. **Data Coverage**: What % of needed variables are available in discovered datasets?
3. **Feasibility**: How feasible is this research (high/medium/low)?
4. **Recommended Approach**: What's the best way to proceed?
5. **Next Steps**: Concrete actions to take next

Return JSON:
{{
  "answer_feasibility": "high" | "medium" | "low",
  "answer_summary": "Brief answer to the research question",
  "data_coverage_pct": 85,
  "available_variables": ["list of variables we found data for"],
  "missing_variables": ["variables we still need"],
  "recommended_approach": "How to proceed with this research",
  "next_steps": [
    "Step 1: ...",
    "Step 2: ..."
  ],
  "challenges": ["Potential challenges or limitations"]
}}"""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": synthesis_prompt}]
        )

        # Extract JSON from response
        response_text = response.content[0].text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            json_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
            json_text = json_text.replace('```json', '').replace('```', '').strip()
        else:
            json_text = response_text

        synthesis = json.loads(json_text)

        self._log_decision(
            f"Research feasibility: {synthesis.get('answer_feasibility')}",
            synthesis.get('answer_summary', ''),
            {
                "data_coverage": f"{synthesis.get('data_coverage_pct', 0)}%",
                "next_steps": len(synthesis.get('next_steps', []))
            }
        )

        return synthesis
