"""
Dataset Discovery Agent

Intelligent agent that searches for relevant datasets across multiple sources:
- CKAN portals (data.gov with 250K+ datasets)
- SODA portals (CDC, CMS, state health departments)
- Other government health data sources

Key features:
- Zero hardcoding - LLM decides which sources to search and how
- Multi-source parallel search
- Intelligent ranking based on hypothesis relevance
- Comprehensive logging of all decisions
"""

import logging
import json
from typing import List, Dict, Optional, Any
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class DatasetDiscoveryAgent:
    """
    Discovers relevant datasets for a research hypothesis.

    Uses LLM to intelligently:
    1. Extract key search terms from hypothesis
    2. Decide which data portals to search
    3. Construct optimal queries for each portal
    4. Rank results by relevance
    """

    def __init__(
        self,
        ckan_client: Any,
        soda_client: Any,
        anthropic_client: AsyncAnthropic,
    ):
        """
        Args:
            ckan_client: CKAN metadata MCP client
            soda_client: SODA API MCP client
            anthropic_client: Anthropic API client for intelligent decisions
        """
        self.ckan_client = ckan_client
        self.soda_client = soda_client
        self.anthropic = anthropic_client
        self.model = "claude-3-7-sonnet-20250219"

    def _log_decision(self, decision: str, reason: str, details: Optional[Dict] = None):
        """Log a decision with reasoning"""
        logger.info(f"[DISCOVERY-DECISION] {decision}")
        logger.info(f"[DISCOVERY-REASON] {reason}")
        if details:
            logger.info(f"[DISCOVERY-DETAILS] {json.dumps(details, indent=2)}")

    def _log_pattern(self, pattern: str, evidence: Optional[Dict] = None):
        """Log a discovered pattern"""
        logger.info(f"[DISCOVERY-PATTERN] {pattern}")
        if evidence:
            logger.info(f"[DISCOVERY-EVIDENCE] {json.dumps(evidence, indent=2)}")

    async def discover(
        self,
        hypothesis: str,
        variables_needed: List[str],
        max_datasets: int = 20
    ) -> Dict[str, Any]:
        """
        Discover datasets relevant to hypothesis.

        Args:
            hypothesis: Research hypothesis
            variables_needed: Variables identified from literature review
            max_datasets: Maximum datasets to return

        Returns:
            {
                'datasets': [
                    {
                        'source': 'ckan' | 'soda',
                        'portal': 'data.gov' | 'data.cdc.gov' | etc,
                        'id': resource_id,
                        'name': dataset_name,
                        'description': description,
                        'relevance_score': 0-100,
                        'relevance_reason': why this dataset is relevant,
                        'variables_available': [list of matching variables],
                        'access_method': 'datastore' | 'soda' | 'download',
                        'url': dataset_url,
                    }
                ],
                'search_strategy': {
                    'portals_searched': [...],
                    'queries_used': {...},
                    'ranking_criteria': [...],
                }
            }
        """
        logger.info(f"[DISCOVERY-AGENT] Starting dataset discovery for hypothesis")
        logger.info(f"[DISCOVERY-AGENT] Variables needed: {variables_needed}")

        # Phase 1: LLM constructs search strategy
        search_strategy = await self._construct_search_strategy(
            hypothesis, variables_needed
        )

        # Phase 2: Execute searches across portals
        all_results = await self._execute_searches(search_strategy)

        # Phase 3: LLM ranks datasets by relevance
        ranked_datasets = await self._rank_datasets(
            hypothesis, variables_needed, all_results
        )

        # Phase 4: Get detailed info for top datasets
        top_datasets = ranked_datasets[:max_datasets]
        enriched_datasets = await self._enrich_dataset_info(top_datasets)

        return {
            'success': True,
            'datasets': enriched_datasets,
            'search_strategy': search_strategy,
            'total_found': len(all_results),
            'total_returned': len(enriched_datasets),
        }

    async def _construct_search_strategy(
        self,
        hypothesis: str,
        variables_needed: List[str]
    ) -> Dict[str, Any]:
        """
        Phase 1: LLM decides search strategy.

        Returns which portals to search and what queries to use.
        """
        logger.info("[DISCOVERY-AGENT] Phase 1: Constructing search strategy")

        strategy_prompt = f"""You are a data discovery expert helping find government health datasets.

Hypothesis: "{hypothesis}"

Variables needed: {json.dumps(variables_needed, indent=2)}

Available data portals:
1. **data.gov (CKAN)**: 250K+ datasets, broad government data, good for NHANES, Census, EPA
2. **data.cdc.gov (SODA)**: CDC health data, BRFSS, NHIS, mortality, infectious disease
3. **data.cms.gov (SODA)**: Medicare/Medicaid data, claims, utilization, outcomes
4. **healthdata.gov (CKAN)**: Health-specific datasets across HHS agencies

For this hypothesis, decide:
1. Which portals to search (and WHY each is relevant)
2. What search queries to use for each portal
3. What filters to apply (tags, categories, time ranges)

Return JSON:
{{
  "portals": [
    {{
      "name": "data.gov" | "data.cdc.gov" | "data.cms.gov" | "healthdata.gov",
      "type": "ckan" | "soda",
      "base_url": "https://...",
      "reason": "Why search this portal",
      "queries": [
        {{
          "query": "search terms",
          "filters": {{"tags": [...], "categories": [...]}},
          "reason": "Why this query will find relevant data"
        }}
      ]
    }}
  ],
  "ranking_criteria": ["What makes a dataset highly relevant for this hypothesis"]
}}

Only recommend portals and queries that will genuinely help. Don't search everything just because you can."""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": strategy_prompt}]
        )

        # Extract JSON from response
        response_text = response.content[0].text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            json_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
            json_text = json_text.replace('```json', '').replace('```', '').strip()
        else:
            json_text = response_text

        strategy = json.loads(json_text)

        self._log_decision(
            f"Searching {len(strategy['portals'])} portals",
            "LLM selected most relevant data sources for hypothesis",
            {
                "portals": [p['name'] for p in strategy['portals']],
                "total_queries": sum(len(p['queries']) for p in strategy['portals'])
            }
        )

        for portal in strategy['portals']:
            self._log_decision(
                f"Will search {portal['name']}",
                portal['reason'],
                {"query_count": len(portal['queries'])}
            )

        return strategy

    async def _execute_searches(self, strategy: Dict[str, Any]) -> List[Dict]:
        """
        Phase 2: Execute searches across selected portals.
        """
        logger.info("[DISCOVERY-AGENT] Phase 2: Executing searches")

        all_results = []

        for portal in strategy['portals']:
            portal_name = portal['name']
            portal_type = portal['type']
            base_url = portal['base_url']

            for query_spec in portal['queries']:
                query = query_spec['query']
                filters = query_spec.get('filters', {})

                self._log_decision(
                    f"Searching {portal_name}: \"{query}\"",
                    query_spec['reason'],
                    {"filters": filters}
                )

                try:
                    if portal_type == 'ckan':
                        # Search CKAN portal
                        result = self.ckan_client.call_tool(
                            'ckan_search',
                            {
                                'base_url': base_url,
                                'query': query,
                                'tags': filters.get('tags'),
                                'limit': 50,
                            }
                        )

                        datasets = result.get('results', [])
                        for dataset in datasets:
                            all_results.append({
                                'source': 'ckan',
                                'portal': portal_name,
                                'base_url': base_url,
                                **dataset,
                            })

                        logger.info(f"[DISCOVERY-AGENT] Found {len(datasets)} datasets on {portal_name}")

                    elif portal_type == 'soda':
                        # Search SODA portal
                        result = self.soda_client.call_tool(
                            'soda_search',
                            {
                                'base_url': base_url,
                                'query': query,
                                'tags': filters.get('tags'),
                                'categories': filters.get('categories'),
                                'limit': 50,
                            }
                        )

                        datasets = result.get('results', [])
                        for dataset in datasets:
                            all_results.append({
                                'source': 'soda',
                                'portal': portal_name,
                                'base_url': base_url,
                                **dataset,
                            })

                        logger.info(f"[DISCOVERY-AGENT] Found {len(datasets)} datasets on {portal_name}")

                except Exception as e:
                    logger.warning(f"[DISCOVERY-WARNING] Search failed on {portal_name}: {str(e)}")

        logger.info(f"[DISCOVERY-AGENT] Total datasets found: {len(all_results)}")

        return all_results

    async def _rank_datasets(
        self,
        hypothesis: str,
        variables_needed: List[str],
        datasets: List[Dict]
    ) -> List[Dict]:
        """
        Phase 3: LLM ranks datasets by relevance.
        """
        logger.info("[DISCOVERY-AGENT] Phase 3: Ranking datasets by relevance")

        if len(datasets) == 0:
            logger.warning("[DISCOVERY-WARNING] No datasets to rank")
            return []

        # For large result sets, batch the ranking
        batch_size = 20
        ranked_batches = []

        for i in range(0, len(datasets), batch_size):
            batch = datasets[i:i + batch_size]

            ranking_prompt = f"""You are evaluating datasets for this research hypothesis:
"{hypothesis}"

Variables needed: {json.dumps(variables_needed)}

Datasets found:
{json.dumps([{'name': d.get('name'), 'description': d.get('description', '')[:200]} for d in batch], indent=2)}

For EACH dataset, provide:
1. **Relevance score** (0-100): How well does it match the hypothesis?
2. **Reason**: WHY is it relevant (or not)?
3. **Variables available**: Which needed variables might be in this dataset?

Return JSON array:
[
  {{
    "index": 0,
    "relevance_score": 85,
    "reason": "Contains NHANES data with BMD and age variables",
    "variables_available": ["age", "bone_mineral_density"]
  }},
  ...
]

Be honest - if a dataset is not relevant, give it a low score."""

            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=3000,
                messages=[{"role": "user", "content": ranking_prompt}]
            )

            # Extract JSON from response
            response_text = response.content[0].text.strip()
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                json_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
                json_text = json_text.replace('```json', '').replace('```', '').strip()
            else:
                json_text = response_text

            rankings = json.loads(json_text)

            # Merge rankings with datasets
            for ranking in rankings:
                idx = ranking['index']
                if idx < len(batch):
                    dataset = batch[idx].copy()
                    dataset['relevance_score'] = ranking['relevance_score']
                    dataset['relevance_reason'] = ranking['reason']
                    dataset['variables_available'] = ranking.get('variables_available', [])
                    ranked_batches.append(dataset)

        # Sort all by relevance score
        ranked_datasets = sorted(ranked_batches, key=lambda x: x.get('relevance_score', 0), reverse=True)

        logger.info(f"[DISCOVERY-AGENT] Ranked {len(ranked_datasets)} datasets")
        if len(ranked_datasets) > 0:
            self._log_pattern(
                f"Top dataset: {ranked_datasets[0].get('name')} (score: {ranked_datasets[0].get('relevance_score')})",
                {"reason": ranked_datasets[0].get('relevance_reason')}
            )

        return ranked_datasets

    async def _enrich_dataset_info(self, datasets: List[Dict]) -> List[Dict]:
        """
        Phase 4: Get detailed metadata for top datasets.
        """
        logger.info(f"[DISCOVERY-AGENT] Phase 4: Enriching {len(datasets)} top datasets")

        enriched = []

        for dataset in datasets:
            try:
                source = dataset.get('source')
                base_url = dataset.get('base_url')
                resource_id = dataset.get('id') or dataset.get('resource_id')

                if not resource_id:
                    enriched.append(dataset)
                    continue

                if source == 'ckan':
                    # Get CKAN resource details
                    resource_info = self.ckan_client.call_tool(
                        'ckan_resource_info',
                        {
                            'base_url': base_url,
                            'resource_id': resource_id,
                        }
                    )

                    dataset['access_method'] = resource_info.get('recommended_access_method', 'download')
                    dataset['format'] = resource_info.get('format')
                    dataset['size'] = resource_info.get('size')
                    dataset['last_modified'] = resource_info.get('last_modified')

                elif source == 'soda':
                    # Get SODA metadata
                    metadata = self.soda_client.call_tool(
                        'soda_metadata',
                        {
                            'base_url': base_url,
                            'resource_id': resource_id,
                        }
                    )

                    dataset['access_method'] = 'soda'
                    dataset['columns'] = metadata.get('columns', [])
                    dataset['row_count'] = metadata.get('row_count')

                enriched.append(dataset)

            except Exception as e:
                logger.warning(f"[DISCOVERY-WARNING] Failed to enrich {dataset.get('name')}: {str(e)}")
                enriched.append(dataset)

        return enriched
