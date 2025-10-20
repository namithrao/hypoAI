"""
Intelligent Literature Discovery Agent

Zero-hardcoded agent that:
1. Finds most relevant papers
2. Analyzes full text to extract variables/biomarkers
3. Uses LLM to decide which databases to link to (genes? proteins? variants?)
4. Discovers patterns across papers
5. Expands search via citations
6. Generates novel hypotheses
"""

import json
import logging
from typing import Any, Dict, List, Optional
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class LiteratureDiscoveryAgent:
    """
    Intelligent agent that analyzes research literature to discover:
    - Relevant variables and biomarkers
    - Cross-database connections (genes, proteins, variants)
    - Patterns and contradictions across papers
    - Novel research hypotheses

    Uses LLM reasoning to decide what to link and why
    """

    def __init__(self, ncbi_client, anthropic_client: AsyncAnthropic):
        """
        Args:
            ncbi_client: NCBI E-utilities MCP client
            anthropic_client: Anthropic API client for analysis
        """
        self.ncbi_client = ncbi_client
        self.anthropic = anthropic_client
        self.model = "claude-3-7-sonnet-20250219"  # Best reasoning model

        # Accumulated findings
        self.papers_analyzed: List[Dict] = []
        self.extracted_variables: List[str] = []
        self.mentioned_genes: List[str] = []
        self.mentioned_variants: List[str] = []
        self.patterns: List[Dict] = []
        self.contradictions: List[Dict] = []
        self.novel_hypotheses: List[str] = []

    def _log_decision(self, decision: str, reason: str, details: Optional[Dict] = None):
        """Log agent decisions with reasoning."""
        logger.info(f"[LIT-AGENT-DECISION] {decision}")
        logger.info(f"[LIT-AGENT-REASON] {reason}")
        if details:
            logger.info(f"[LIT-AGENT-DETAILS] {json.dumps(details, indent=2)}")

    def _log_pattern(self, pattern: str, evidence: Dict):
        """Log discovered patterns."""
        logger.info(f"[LIT-AGENT-PATTERN] {pattern}")
        logger.info(f"[LIT-AGENT-EVIDENCE] {json.dumps(evidence, indent=2)}")

    def _log_novel(self, hypothesis: str, reasoning: str):
        """Log novel hypotheses."""
        logger.info(f"[LIT-AGENT-NOVEL] {hypothesis}")
        logger.info(f"[LIT-AGENT-REASONING] {reasoning}")

    async def analyze(self, hypothesis: str, max_papers: int = 50) -> Dict[str, Any]:
        """
        Main entry point: Analyze literature for a hypothesis.

        Args:
            hypothesis: Research question/hypothesis
            max_papers: Maximum papers to analyze

        Returns:
            Dictionary with all findings
        """
        logger.info(f"[LIT-AGENT] Starting literature analysis for: {hypothesis}")

        # Phase 1: Find most relevant papers
        relevant_papers = await self._find_relevant_papers(hypothesis, max_papers)

        # Phase 2: Analyze top papers in detail
        top_papers = relevant_papers[:min(10, len(relevant_papers))]
        await self._analyze_papers_in_depth(top_papers, hypothesis)

        # Phase 3: LLM decides what cross-database links to follow
        await self._intelligent_cross_database_linking(hypothesis)

        # Phase 4: Expand via citations of most important papers
        await self._expand_via_citations(top_papers[:5])

        # Phase 5: Synthesize findings and generate novel hypotheses
        synthesis = await self._synthesize_findings(hypothesis)

        return synthesis

    async def _find_relevant_papers(self, hypothesis: str, max_results: int) -> List[Dict]:
        """
        Phase 1: Find most relevant papers using intelligent query construction.
        """
        logger.info(f"[LIT-AGENT] Phase 1: Finding relevant papers")

        # Ask LLM to construct optimal PubMed search query
        query_prompt = f"""You are a research librarian expert at PubMed searches.

Given this hypothesis:
"{hypothesis}"

Construct an optimal PubMed search query using Boolean operators (AND, OR, NOT) and MeSH terms.

Guidelines:
- Include key concepts from the hypothesis
- Use OR for synonyms
- Use AND to combine concepts
- Consider MeSH terms for precise medical concepts
- Keep query focused but not too narrow

Return ONLY the search query, nothing else."""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": query_prompt}]
        )

        search_query = response.content[0].text.strip()

        self._log_decision(
            f"Constructed PubMed search query",
            f"LLM-generated query designed to find papers matching hypothesis concepts",
            {"query": search_query, "hypothesis": hypothesis}
        )

        # Search PubMed
        search_results = self.ncbi_client.call_tool(
            "ncbi_search",
            {
                "db": "pubmed",
                "term": search_query,
                "retmax": max_results,
                "mindate": "2010/01/01"  # Recent papers for current methods
            }
        )

        pmids = search_results['ids']
        logger.info(f"[LIT-AGENT] Found {len(pmids)} papers")

        # Get summaries for ranking
        papers = []
        for pmid in pmids[:max_results]:
            summary = self.ncbi_client.call_tool(
                "ncbi_summary",
                {"db": "pubmed", "id": pmid}
            )
            papers.append({
                "pmid": pmid,
                "title": summary.get(pmid, {}).get('title', ''),
                "pubdate": summary.get(pmid, {}).get('pubdate', ''),
            })

        return papers

    async def _analyze_papers_in_depth(self, papers: List[Dict], hypothesis: str):
        """
        Phase 2: Deep analysis of top papers.

        For each paper:
        1. Fetch full abstract (or full text if available)
        2. LLM extracts: variables, methods, outcomes, genes, proteins, etc.
        """
        logger.info(f"[LIT-AGENT] Phase 2: Analyzing {len(papers)} papers in depth")

        for paper in papers:
            pmid = paper['pmid']

            # Fetch abstract
            abstract_data = self.ncbi_client.call_tool(
                "ncbi_fetch",
                {"db": "pubmed", "id": pmid, "rettype": "abstract"}
            )

            # Try to get full text from PMC
            pmc_links = self.ncbi_client.call_tool(
                "ncbi_link",
                {"dbfrom": "pubmed", "db": "pmc", "id": pmid}
            )

            full_text = None
            if pmc_links.get('linked_ids'):
                pmc_id = pmc_links['linked_ids'][0]
                try:
                    full_text_data = self.ncbi_client.call_tool(
                        "ncbi_fetch",
                        {"db": "pmc", "id": pmc_id}
                    )
                    full_text = full_text_data.get('raw_text', '')
                    self._log_decision(
                        f"Retrieved full text for PMID:{pmid}",
                        f"Full text provides complete methods and results",
                        {"pmid": pmid, "pmc_id": pmc_id}
                    )
                except:
                    pass

            # LLM analyzes the paper
            text_to_analyze = full_text if full_text else str(abstract_data)

            analysis_prompt = f"""You are analyzing a research paper for this hypothesis:
"{hypothesis}"

Paper text:
{text_to_analyze[:8000]}  # Limit to fit context

Extract and categorize:

1. **Variables/Biomarkers measured**: What did they measure? (e.g., bone mineral density, age, CRP)
2. **Outcomes studied**: What were they trying to predict? (e.g., fracture healing time, mortality)
3. **Population**: Who was studied? (age range, conditions, etc.)
4. **Data sources cited**: Did they mention datasets? (NHANES, Medicare, UK Biobank, etc.)
5. **Biological entities**: Genes, proteins, genetic variants mentioned
6. **Statistical methods**: What tests did they use?
7. **Key findings**: What did they conclude?
8. **Limitations**: What did they say was missing or needed?

Return as JSON with these exact keys:
{{
  "variables_measured": [...],
  "outcomes": [...],
  "population": "...",
  "data_sources_cited": [...],
  "genes_mentioned": [...],
  "proteins_mentioned": [...],
  "variants_mentioned": [...],
  "statistical_methods": [...],
  "key_findings": "...",
  "limitations": "...",
  "relevance_to_hypothesis": "high/medium/low"
}}"""

            response = await self.anthropic.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": analysis_prompt}]
            )

            try:
                # Extract JSON from response (handle markdown code blocks)
                response_text = response.content[0].text.strip()
                if response_text.startswith('```'):
                    # Extract JSON from markdown code block
                    lines = response_text.split('\n')
                    json_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
                    json_text = json_text.replace('```json', '').replace('```', '').strip()
                else:
                    json_text = response_text

                analysis = json.loads(json_text)

                # Store analysis
                paper['analysis'] = analysis
                self.papers_analyzed.append(paper)

                # Accumulate findings
                self.extracted_variables.extend(analysis.get('variables_measured', []))
                self.mentioned_genes.extend(analysis.get('genes_mentioned', []))
                self.mentioned_variants.extend(analysis.get('variants_mentioned', []))

                self._log_decision(
                    f"Analyzed PMID:{pmid} - Relevance: {analysis.get('relevance_to_hypothesis')}",
                    f"Extracted {len(analysis.get('variables_measured', []))} variables, "
                    f"{len(analysis.get('genes_mentioned', []))} genes",
                    {
                        "pmid": pmid,
                        "title": paper.get('title', f'Paper {pmid}'),
                        "variables": analysis.get('variables_measured', [])[:5],
                        "genes": analysis.get('genes_mentioned', [])[:5],
                    }
                )

            except json.JSONDecodeError:
                logger.warning(f"[LIT-AGENT-WARNING] Failed to parse analysis for PMID:{pmid}")

    async def _intelligent_cross_database_linking(self, hypothesis: str):
        """
        Phase 3: LLM decides which cross-database links to follow and WHY.
        """
        logger.info(f"[LIT-AGENT] Phase 3: Intelligent cross-database linking")

        # Prepare summary of what we found
        summary = {
            "papers_analyzed": len(self.papers_analyzed),
            "unique_genes_mentioned": list(set(self.mentioned_genes)),
            "unique_variants_mentioned": list(set(self.mentioned_variants)),
            "common_variables": self._find_common_elements(self.extracted_variables, min_count=3),
        }

        # Ask LLM: What links would be valuable?
        linking_prompt = f"""You are a research strategist analyzing literature for:
"{hypothesis}"

So far we've analyzed {summary['papers_analyzed']} papers and found:
- {len(summary['unique_genes_mentioned'])} unique genes mentioned: {summary['unique_genes_mentioned'][:10]}
- {len(summary['unique_variants_mentioned'])} unique variants mentioned: {summary['unique_variants_mentioned'][:5]}
- Common variables across papers: {summary['common_variables'][:10]}

Available NCBI databases to link to:
- gene: Gene information
- protein: Protein sequences and structures
- clinvar: Genetic variants and clinical significance
- omim: Genetic disorders
- gtr: Genetic testing

**Decide which cross-database links would provide valuable insights for this hypothesis.**

For EACH link you recommend, explain:
1. What to link (which genes/papers)
2. Which database to link to
3. WHY this link would help answer the hypothesis
4. What insight you hope to gain

Return as JSON:
{{
  "recommended_links": [
    {{
      "link_type": "gene_to_clinvar",
      "items": ["GENE_NAME1", "GENE_NAME2"],
      "reason": "...",
      "expected_insight": "..."
    }},
    ...
  ],
  "skip_links": [
    {{
      "link_type": "...",
      "reason_to_skip": "..."
    }}
  ]
}}

Only recommend links that would genuinely help. Don't link just because you can."""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": linking_prompt}]
        )

        try:
            # Extract JSON from response (handle markdown code blocks)
            response_text = response.content[0].text.strip()
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                json_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
                json_text = json_text.replace('```json', '').replace('```', '').strip()
            else:
                json_text = response_text

            link_plan = json.loads(json_text)

            # Execute recommended links
            for link in link_plan.get('recommended_links', []):
                self._log_decision(
                    f"Following link: {link['link_type']}",
                    link['reason'],
                    {"expected_insight": link['expected_insight']}
                )

                # Execute the link
                await self._execute_intelligent_link(link)

            # Log skipped links
            for skip in link_plan.get('skip_links', []):
                logger.info(f"[LIT-AGENT-SKIP] Skipping {skip['link_type']}: {skip['reason_to_skip']}")

        except json.JSONDecodeError:
            logger.warning("[LIT-AGENT-WARNING] Failed to parse linking plan")

    async def _execute_intelligent_link(self, link_spec: Dict):
        """Execute a specific cross-database link based on LLM recommendation."""

        link_type = link_spec['link_type']
        items = link_spec.get('items', [])

        # Map link types to NCBI operations
        if link_type == "gene_to_clinvar":
            # For each gene, find variants
            for gene_name in items[:5]:  # Limit to avoid rate limits
                # First need to find gene ID from name
                gene_search = self.ncbi_client.call_tool(
                    "ncbi_search",
                    {"db": "gene", "term": f"{gene_name}[Gene Name] AND Homo sapiens[Organism]", "retmax": 1}
                )

                if gene_search['ids']:
                    gene_id = gene_search['ids'][0]

                    # Link to ClinVar
                    variants = self.ncbi_client.call_tool(
                        "ncbi_link",
                        {"dbfrom": "gene", "db": "clinvar", "id": gene_id}
                    )

                    if variants.get('linked_ids'):
                        self._log_pattern(
                            f"Gene {gene_name} has {len(variants['linked_ids'])} ClinVar variants",
                            {
                                "gene": gene_name,
                                "gene_id": gene_id,
                                "variant_count": len(variants['linked_ids']),
                                "insight": link_spec['expected_insight']
                            }
                        )

        # Add more link type handlers as needed
        # The LLM decides which links to follow - we just execute them

    async def _expand_via_citations(self, papers: List[Dict]):
        """
        Phase 4: Expand search via citations of most important papers.

        LLM decides which papers are "important enough" to follow citations.
        """
        logger.info(f"[LIT-AGENT] Phase 4: Expanding via citations")

        for paper in papers:
            pmid = paper['pmid']

            # Find papers that cite this one
            citing_papers = self.ncbi_client.call_tool(
                "ncbi_link",
                {"dbfrom": "pubmed", "db": "pubmed", "id": pmid}
            )

            if citing_papers.get('linked_ids'):
                self._log_decision(
                    f"Found {len(citing_papers['linked_ids'])} papers citing PMID:{pmid}",
                    f"Highly relevant paper - citations may provide updated findings",
                    {"pmid": pmid, "title": paper.get('title', ''), "citation_count": len(citing_papers['linked_ids'])}
                )

                # Analyze top 5 citing papers
                for citing_pmid in citing_papers['linked_ids'][:5]:
                    if citing_pmid not in [p['pmid'] for p in self.papers_analyzed]:
                        # Add to analysis queue
                        await self._analyze_papers_in_depth([{"pmid": citing_pmid}], "")

    async def _synthesize_findings(self, hypothesis: str) -> Dict[str, Any]:
        """
        Phase 5: LLM synthesizes all findings to generate novel hypotheses.

        Looks for:
        - Patterns across papers
        - Contradictions
        - Research gaps
        - Novel connections
        """
        logger.info(f"[LIT-AGENT] Phase 5: Synthesizing findings")

        # Prepare comprehensive summary
        all_variables = list(set(self.extracted_variables))
        all_genes = list(set(self.mentioned_genes))

        synthesis_prompt = f"""You analyzed {len(self.papers_analyzed)} papers for:
"{hypothesis}"

Findings:
- Variables mentioned: {all_variables[:30]}
- Genes mentioned: {all_genes[:20]}
- Papers from {self.papers_analyzed[0]['pubdate'] if self.papers_analyzed else 'N/A'} to present

Analyze these findings and identify:

1. **Patterns**: What variables/concepts appear together across multiple papers?
2. **Contradictions**: Where do papers disagree?
3. **Gaps**: What's missing? What hasn't been studied?
4. **Novel Hypotheses**: What NEW research questions emerge from connecting these findings?
5. **Data Recommendations**: What datasets (NHANES, Medicare, UK Biobank, etc.) could help?

Return as JSON:
{{
  "patterns": [...],
  "contradictions": [...],
  "research_gaps": [...],
  "novel_hypotheses": [...],
  "recommended_variables": [...],
  "recommended_data_sources": [...],
  "synthesis_summary": "..."
}}"""

        response = await self.anthropic.messages.create(
            model=self.model,
            max_tokens=3000,
            messages=[{"role": "user", "content": synthesis_prompt}]
        )

        # Extract JSON from response (handle markdown code blocks)
        response_text = response.content[0].text.strip()
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            json_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
            json_text = json_text.replace('```json', '').replace('```', '').strip()
        else:
            json_text = response_text

        synthesis = json.loads(json_text)

        # Log novel hypotheses
        for hypothesis in synthesis.get('novel_hypotheses', []):
            self._log_novel(hypothesis, "Emerged from cross-paper synthesis")

        # Log patterns
        for pattern in synthesis.get('patterns', []):
            self._log_pattern(pattern, {"source": "multi-paper analysis"})

        return {
            "success": True,
            "papers_analyzed": len(self.papers_analyzed),
            "synthesis": synthesis,
            "all_variables": all_variables,
            "all_genes": all_genes,
        }

    def _find_common_elements(self, items: List[str], min_count: int = 2) -> List[str]:
        """Find elements that appear at least min_count times."""
        from collections import Counter
        counts = Counter(items)
        return [item for item, count in counts.items() if count >= min_count]