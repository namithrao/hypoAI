"""
Literature Discovery Agent V2 - MVP Implementation

Simplified single-agent architecture using:
- Claude API for complex chain-of-thought reasoning
- BlueBERT for medical entity extraction
- MCP for PubMed access
- Iterative search until 10+ variables discovered

Key Features:
- Takes medical hypothesis as input
- Searches PubMed via MCP
- Analyzes papers with Claude (CoT reasoning)
- Extracts variables, confounders, relationships
- Iteratively expands search (citations, related papers) if needed
- Outputs structured JSON with citations
"""

import json
import logging
import asyncio
import time
from typing import Any, Dict, List, Optional, Set
from anthropic import AsyncAnthropic
from transformers import pipeline
import xml.etree.ElementTree as ET
import httpx

logger = logging.getLogger(__name__)


class LiteratureDiscoveryAgentV2:
    """
    MVP Literature Discovery Agent.

    Single-agent pipeline for discovering variables from medical research papers.
    """

    def __init__(
        self,
        ncbi_client: Any,
        anthropic_client: AsyncAnthropic,
        ncbi_api_key: Optional[str] = None
    ):
        """
        Args:
            ncbi_client: NCBI E-utilities MCP client (not used, kept for compatibility)
            anthropic_client: Claude API client
            ncbi_api_key: NCBI E-utilities API key (10 req/s with key vs 3 req/s without)
        """
        self.ncbi_client = ncbi_client
        self.anthropic = anthropic_client
        self.ncbi_api_key = ncbi_api_key
        self.claude_model = "claude-haiku-4-5-20251001"  # Claude Haiku 4.5 for testing

        # Rate limiting (10 req/s with API key, 3 req/s without)
        self.last_ncbi_request_time = 0.0
        self.min_request_interval = 0.11  # 110ms = ~9 req/s (safe buffer under 10 req/s limit)

        # BioBERT NER setup (lazy loading)
        self.chemical_ner = None  # For biomarkers like CRP, glucose, etc.
        self.disease_ner = None   # For diseases like Type 2 Diabetes, CVD, etc.
        self.recognized_entities: Dict[str, Set[str]] = {}  # Store extracted entities

        # State tracking
        self.hypothesis: str = ""
        self.papers_analyzed: List[Dict] = []
        self.variables_discovered: List[Dict] = []
        self.confounders: List[Dict] = []
        self.relationships: List[Dict] = []

    def _load_biobert_ner(self):
        """Lazy load BioBERT NER models (only when needed)."""
        if self.chemical_ner is None or self.disease_ner is None:
            logger.info("Loading BioBERT NER models (Chemical + Disease)...")

            try:
                # Chemical NER (for biomarkers like CRP, glucose, etc.)
                self.chemical_ner = pipeline(
                    "ner",
                    model="alvaroalon2/biobert_chemical_ner",
                    aggregation_strategy="simple",  # Merge B-CHEMICAL, I-CHEMICAL into one entity
                    device=-1  # Use CPU (change to 0 for GPU)
                )

                # Disease NER (for diseases like Type 2 Diabetes, CVD, etc.)
                self.disease_ner = pipeline(
                    "ner",
                    model="alvaroalon2/biobert_diseases_ner",
                    aggregation_strategy="simple",
                    device=-1  # Use CPU
                )

                logger.info("BioBERT NER models loaded successfully (Chemical + Disease)")
            except Exception as e:
                logger.error(f"Failed to load BioBERT NER models: {e}")
                logger.warning("Continuing without NER - variable deduplication may be less effective")
                # Set to empty pipelines to avoid repeated load attempts
                self.chemical_ner = False
                self.disease_ner = False

    async def _rate_limit(self):
        """Enforce rate limiting for NCBI API requests."""
        elapsed = time.time() - self.last_ncbi_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            await asyncio.sleep(sleep_time)
        self.last_ncbi_request_time = time.time()

    async def _ncbi_request_with_retry(
        self,
        url: str,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> httpx.Response:
        """
        Make NCBI API request with rate limiting and retry logic.

        Args:
            url: NCBI E-utilities endpoint URL
            params: Request parameters
            max_retries: Maximum number of retry attempts

        Returns:
            Response from NCBI

        Raises:
            httpx.HTTPStatusError: If request fails after all retries
        """
        # Add API key if available
        if self.ncbi_api_key:
            params['api_key'] = self.ncbi_api_key

        for attempt in range(max_retries):
            try:
                # Rate limit
                await self._rate_limit()

                # Make request
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    return response

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"[NCBI] Rate limited (429), retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                elif e.response.status_code >= 500:  # Server error
                    wait_time = 2 ** attempt
                    logger.warning(f"[NCBI] Server error ({e.response.status_code}), retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    # Client error (4xx except 429), don't retry
                    raise

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                wait_time = 2 ** attempt
                logger.warning(f"[NCBI] Network error ({e}), retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)

        # If we get here, all retries failed
        raise httpx.HTTPStatusError(
            f"NCBI request failed after {max_retries} retries",
            request=response.request,
            response=response
        )

    async def _search_pubmed_http(self, query: str, max_results: int = 50) -> List[str]:
        """
        Search PubMed using NCBI E-utilities ESearch.

        Returns list of PMIDs.
        """
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "xml",
            "usehistory": "y",
            "mindate": "2015/01/01",
            "datetype": "pdat"
        }

        response = await self._ncbi_request_with_retry(base_url, params)

        # Parse XML response
        root = ET.fromstring(response.text)
        pmids = [id_elem.text for id_elem in root.findall(".//Id")]

        logger.info(f"[NCBI ESearch] Found {len(pmids)} PMIDs for query: {query}")
        return pmids

    async def _get_summaries_http(self, pmids: List[str]) -> Dict[str, Dict]:
        """
        Get paper summaries using NCBI E-utilities ESummary.

        Returns dict mapping PMID to metadata.
        """
        if not pmids:
            return {}

        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "version": "2.0",
            "retmode": "xml"
        }

        response = await self._ncbi_request_with_retry(base_url, params)

        # Parse XML response
        root = ET.fromstring(response.text)
        summaries = {}

        for doc_sum in root.findall(".//DocumentSummary"):
            pmid = doc_sum.get("uid")
            title = ""
            authors = []
            journal = ""
            year = ""
            doi = ""

            for item in doc_sum.findall("./Item"):
                name = item.get("Name")
                if name == "Title":
                    title = item.text or ""
                elif name == "Source":
                    journal = item.text or ""
                elif name == "PubDate":
                    year = (item.text or "").split()[0]  # Extract year
                elif name == "DOI":
                    doi = item.text or ""
                elif name == "AuthorList":
                    for author_item in item.findall("./Item"):
                        if author_item.text:
                            authors.append(author_item.text)

            summaries[pmid] = {
                "title": title,
                "authors": authors,
                "journal": journal,
                "year": year,
                "doi": doi
            }

        logger.info(f"[NCBI ESummary] Retrieved {len(summaries)} paper summaries")
        return summaries

    async def _get_abstract_xml(self, pmid: str) -> Dict[str, Any]:
        """
        Get abstract XML using NCBI E-utilities EFetch.

        Returns dict with abstract sections and keywords.
        """
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": pmid,
            "retmode": "xml"
        }

        response = await self._ncbi_request_with_retry(base_url, params)

        # Parse XML response
        root = ET.fromstring(response.text)

        # Extract abstract sections
        abstract_sections = {}
        abstract_elem = root.find(".//Abstract")

        if abstract_elem is not None:
            for abstract_text in abstract_elem.findall("./AbstractText"):
                label = abstract_text.get("Label", "").lower()
                text = "".join(abstract_text.itertext())

                if label in ["background", "objective", "introduction"]:
                    abstract_sections["background"] = text
                elif label in ["methods", "materials and methods"]:
                    abstract_sections["methods"] = text
                elif label in ["results", "findings"]:
                    abstract_sections["results"] = text
                elif label in ["conclusion", "conclusions"]:
                    abstract_sections["conclusions"] = text
                elif not label:  # Unstructured abstract
                    abstract_sections["full"] = text

        # Extract keywords
        keywords = []
        for keyword_elem in root.findall(".//Keyword"):
            if keyword_elem.text:
                keywords.append(keyword_elem.text)

        # Extract publication types
        pub_types = []
        for pub_type_elem in root.findall(".//PublicationType"):
            if pub_type_elem.text:
                pub_types.append(pub_type_elem.text)

        return {
            "abstract_sections": abstract_sections,
            "keywords": keywords,
            "publication_types": pub_types
        }

    async def _check_pmc_available(self, pmid: str) -> Optional[str]:
        """
        Check if paper is available in PMC using NCBI E-utilities ELink.

        Returns PMC ID if available, None otherwise.
        """
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
        params = {
            "dbfrom": "pubmed",
            "db": "pmc",
            "id": pmid,
            "retmode": "xml"
        }

        response = await self._ncbi_request_with_retry(base_url, params)

        # Parse XML response
        root = ET.fromstring(response.text)

        # Look for PMC ID in LinkSetDb
        for link in root.findall(".//Link"):
            id_elem = link.find("./Id")
            if id_elem is not None and id_elem.text:
                pmc_id = id_elem.text
                logger.info(f"[NCBI ELink] PMID:{pmid} available in PMC: PMC{pmc_id}")
                return pmc_id

        logger.info(f"[NCBI ELink] PMID:{pmid} not available in PMC")
        return None

    async def _get_pmc_full_text(self, pmc_id: str) -> Dict[str, str]:
        """
        Get full text from PMC using NCBI E-utilities EFetch.

        Returns dict with full text sections.
        """
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            "db": "pmc",
            "id": pmc_id,
            "retmode": "xml"
        }

        response = await self._ncbi_request_with_retry(base_url, params)

        # Parse XML response
        root = ET.fromstring(response.text)

        sections = {}

        # Extract sections from body
        body = root.find(".//body")
        if body is not None:
            for sec in body.findall(".//sec"):
                # Get section title
                title_elem = sec.find("./title")
                section_title = title_elem.text.lower() if title_elem is not None and title_elem.text else ""

                # Get section text
                section_text = " ".join(sec.itertext()).strip()

                # Categorize section
                if any(kw in section_title for kw in ["introduction", "background"]):
                    sections["introduction"] = section_text
                elif any(kw in section_title for kw in ["method", "material"]):
                    sections["methods"] = section_text
                elif any(kw in section_title for kw in ["result", "finding"]):
                    sections["results"] = section_text
                elif any(kw in section_title for kw in ["discussion"]):
                    sections["discussion"] = section_text
                elif any(kw in section_title for kw in ["conclusion"]):
                    sections["conclusions"] = section_text

        logger.info(f"[NCBI EFetch PMC] Extracted {len(sections)} sections from PMC{pmc_id}")
        return sections

    def _log_decision(self, decision: str, reason: str, details: Optional[Dict] = None):
        """Log agent decision with reasoning."""
        logger.info(f"[LIT-AGENT-DECISION] {decision}")
        logger.info(f"[LIT-AGENT-REASON] {reason}")
        if details:
            logger.info(f"[LIT-AGENT-DETAILS] {json.dumps(details, indent=2)}")

    async def discover_variables(
        self,
        hypothesis: str,
        min_variables: int = 10,
        max_papers: int = 50,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Main entry point: Discover variables for a medical hypothesis.

        Args:
            hypothesis: Medical research hypothesis
            min_variables: Minimum variables to discover before stopping
            max_papers: Maximum papers to analyze
            max_iterations: Maximum search iterations

        Returns:
            {
                "hypothesis": original hypothesis,
                "variables": [
                    {
                        "name": "CRP",
                        "type": "continuous",
                        "role": "predictor",
                        "relationship": "positive",
                        "citations": ["PMID:123"],
                        "reasoning": "..."
                    }
                ],
                "confounders": [...],
                "relationships": [...],
                "papers_analyzed": 15,
                "reasoning_chain": "...",
                "success": true
            }
        """
        logger.info(f"[LIT-AGENT] Starting variable discovery for: {hypothesis}")
        self.hypothesis = hypothesis

        # Step 1: Analyze hypothesis and generate search strategy
        search_strategy = await self._analyze_hypothesis(hypothesis)

        # Step 2: Iterative search loop
        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            logger.info(f"[LIT-AGENT] Iteration {iteration}/{max_iterations}")
            logger.info(f"[LIT-AGENT] Current variables: {len(self.variables_discovered)}")

            # Search PubMed
            papers = await self._search_pubmed(
                query=search_strategy['query'],
                max_results=max_papers // max_iterations
            )

            # Analyze papers with Claude
            await self._analyze_papers(papers)

            # Extract entities with BioBERT NER
            await self._extract_medical_entities()

            # Standardize variable names (deduplicate using NER)
            self._standardize_variable_names()

            # Filter out study statistics (not actual variables)
            self._filter_non_variables()

            # Check if we have enough variables
            if len(self.variables_discovered) >= min_variables:
                self._log_decision(
                    f"Found {len(self.variables_discovered)} variables (>= {min_variables})",
                    "Sufficient variables discovered, stopping search",
                    {"iteration": iteration, "total_papers": len(self.papers_analyzed)}
                )
                break

            # Expand search if needed
            if iteration < max_iterations:
                logger.info(f"[LIT-AGENT] Need more variables, expanding search...")
                search_strategy = await self._expand_search_strategy(search_strategy)

        # Step 3: Synthesize findings
        synthesis = await self._synthesize_findings()

        # Build dual output system
        # 1. synthesis_input: minimal data for generator
        synthesis_input = self._build_synthesis_input(hypothesis)

        # 2. literature_display: full metadata for frontend
        literature_display = self._build_literature_display(hypothesis, iteration, synthesis)

        return (synthesis_input, literature_display)

    async def _analyze_hypothesis(self, hypothesis: str) -> Dict[str, Any]:
        """Step 1: Analyze hypothesis and create search strategy."""

        prompt = f"""You are a medical research expert. Analyze this hypothesis and create a PubMed search strategy.

<hypothesis>{hypothesis}</hypothesis>

Think step-by-step:
1. What are the key medical concepts?
2. What variables might we need to measure?
3. What search terms would find relevant papers?

Return ONLY this XML structure (no other text):
<strategy>
  <query>optimal PubMed search query with AND/OR operators</query>
  <key_concepts>
    <concept>concept1</concept>
    <concept>concept2</concept>
  </key_concepts>
  <expected_variable_types>
    <type>biomarker</type>
    <type>demographic</type>
    <type>outcome</type>
  </expected_variable_types>
  <reasoning>why this search strategy will work</reasoning>
</strategy>"""

        response = await self.anthropic.messages.create(
            model=self.claude_model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        strategy_xml = self._extract_xml(response.content[0].text, "strategy")

        # Convert XML to dict
        strategy = {
            "query": strategy_xml.findtext("./query", ""),
            "key_concepts": [c.text for c in strategy_xml.findall("./key_concepts/concept") if c.text],
            "expected_variable_types": [t.text for t in strategy_xml.findall("./expected_variable_types/type") if t.text],
            "reasoning": strategy_xml.findtext("./reasoning", "")
        }

        self._log_decision(
            "Created search strategy",
            strategy['reasoning'],
            {"query": strategy['query'], "concepts": strategy['key_concepts']}
        )

        return strategy

    async def _search_pubmed(self, query: str, max_results: int = 20) -> List[Dict]:
        """Search PubMed via direct HTTP E-utilities."""

        logger.info(f"[LIT-AGENT] Searching PubMed: '{query}'")

        # Step 1: Search for PMIDs
        pmids = await self._search_pubmed_http(query, max_results)
        logger.info(f"[LIT-AGENT] Found {len(pmids)} papers")

        if not pmids:
            return []

        # Step 2: Get summaries for all PMIDs
        summaries = await self._get_summaries_http(pmids)

        # Step 3: Fetch detailed data for each paper
        papers = []
        for pmid in pmids[:max_results]:
            # Get abstract and keywords
            abstract_data = await self._get_abstract_xml(pmid)

            # Check if PMC full text is available
            pmc_id = await self._check_pmc_available(pmid)
            full_text_sections = {}
            if pmc_id:
                full_text_sections = await self._get_pmc_full_text(pmc_id)

            summary = summaries.get(pmid, {})

            papers.append({
                "pmid": pmid,
                "doi": summary.get("doi", ""),
                "title": summary.get("title", ""),
                "authors": summary.get("authors", []),
                "journal": summary.get("journal", ""),
                "year": summary.get("year", ""),
                "abstract_sections": abstract_data.get("abstract_sections", {}),
                "keywords": abstract_data.get("keywords", []),
                "publication_types": abstract_data.get("publication_types", []),
                "pmc_id": pmc_id,
                "full_text_sections": full_text_sections
            })

        return papers

    async def _analyze_papers(self, papers: List[Dict]):
        """Analyze papers with Claude's chain-of-thought reasoning."""

        logger.info(f"[LIT-AGENT] Analyzing {len(papers)} papers with Claude")

        for paper in papers:
            pmid = paper['pmid']
            title = paper['title']

            # Build abstract text from sections or full text
            abstract_sections = paper.get('abstract_sections', {})
            if 'full' in abstract_sections:
                abstract_text = abstract_sections['full']
            else:
                abstract_text = ' '.join([
                    f"{k.title()}: {v}"
                    for k, v in abstract_sections.items()
                ])

            # Claude analyzes paper with CoT reasoning
            prompt = f"""You are analyzing a research paper for this hypothesis:
<hypothesis>{self.hypothesis}</hypothesis>

<paper>
  <pmid>{pmid}</pmid>
  <title>{title}</title>
  <abstract>{abstract_text[:2000]}</abstract>
</paper>

Think step-by-step:
1. What variables are measured in this study?
2. What is the relationship to our hypothesis?
3. Are these predictors, outcomes, or confounders?
4. What correlations/distributions are reported?

For EACH variable, extract:
- name (use standard medical terminology, preferably abbreviations when common)
- type (continuous, categorical, binary, ordinal)
- distribution (normal, lognormal, binomial, etc. - ESTIMATE if not explicitly stated)
- role (predictor, outcome, confounder)
- relationship direction (positive, negative, null, unknown)
- units if mentioned
- typical range (min, max, mean, sd) - PRIORITIZE mean/SD, then min/max
  * If exact values not in abstract, check methods/results sections
  * ESTIMATE reasonable clinical ranges if values not stated but variable is well-known
  * For common biomarkers, use typical clinical reference ranges

IMPORTANT:
- Extract actual measured VARIABLES only (biomarkers, demographics, clinical measures)
- DO NOT extract study statistics (hazard ratios, odds ratios, p-values, etc.)
- Focus on data that would be useful for synthetic dataset generation

Return ONLY this XML structure:
<analysis>
  <variables>
    <variable>
      <name>Biomarker_X</name>
      <type>continuous</type>
      <distribution>lognormal</distribution>
      <role>predictor</role>
      <relationship>positive</relationship>
      <units>mg/L</units>
      <range min="0.5" max="15.0" mean="3.2" sd="2.1"/>
      <reasoning>Study measured this biomarker as primary predictor; elevated levels associated with outcome</reasoning>
    </variable>
    <variable>
      <name>Age</name>
      <type>continuous</type>
      <distribution>normal</distribution>
      <role>confounder</role>
      <relationship>unknown</relationship>
      <units>years</units>
      <range min="45" max="75" mean="58.5" sd="8.2"/>
      <reasoning>Demographic variable controlled in analysis</reasoning>
    </variable>
  </variables>
  <key_findings>summary of paper's main results</key_findings>
  <relevance>high</relevance>
</analysis>"""

            response = await self.anthropic.messages.create(
                model=self.claude_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis_xml = self._extract_xml(response.content[0].text, "analysis")

            # Helper function to safely convert to float
            def safe_float(value: Optional[str]) -> Optional[float]:
                """Convert string to float, handling 'unknown' and invalid values."""
                if not value or value.lower() in ('unknown', 'n/a', 'na', 'none', ''):
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None

            # Parse variables from XML
            variables = []
            for var_elem in analysis_xml.findall(".//variable"):
                range_elem = var_elem.find("./range")
                variable = {
                    "name": var_elem.findtext("./name", ""),
                    "type": var_elem.findtext("./type", "continuous"),
                    "distribution": var_elem.findtext("./distribution", "unknown"),
                    "role": var_elem.findtext("./role", "predictor"),
                    "relationship": var_elem.findtext("./relationship", "unknown"),
                    "units": var_elem.findtext("./units"),
                    "range": {
                        "min": safe_float(range_elem.get("min")) if range_elem is not None else None,
                        "max": safe_float(range_elem.get("max")) if range_elem is not None else None,
                        "mean": safe_float(range_elem.get("mean")) if range_elem is not None else None,
                        "sd": safe_float(range_elem.get("sd")) if range_elem is not None else None,
                    } if range_elem is not None else None,
                    "reasoning": var_elem.findtext("./reasoning", ""),
                    "citations": [f"PMID:{pmid}"]
                }
                variables.append(variable)

            analysis = {
                "variables": variables,
                "key_findings": analysis_xml.findtext("./key_findings", ""),
                "relevance": analysis_xml.findtext("./relevance", "medium")
            }

            # Store results
            paper['analysis'] = analysis
            paper['variables_extracted'] = [v['name'] for v in variables]
            self.papers_analyzed.append(paper)

            # Add variables with citations
            for var in variables:
                # Categorize by role
                if var['role'] == 'confounder':
                    self.confounders.append(var)
                else:
                    self.variables_discovered.append(var)

            self._log_decision(
                f"Analyzed PMID:{pmid}",
                f"Relevance: {analysis.get('relevance')}, Variables: {len(variables)}",
                {"pmid": pmid, "title": title[:80]}
            )

    async def _extract_medical_entities(self):
        """
        Extract standardized medical entities using BioBERT NER.

        This validates and standardizes variable names extracted by Claude.
        """
        logger.info("[BioBERT-NER] Extracting medical entities from papers")

        # Load BioBERT NER if not already loaded
        self._load_biobert_ner()

        # Skip if models failed to load
        if self.chemical_ner is False or self.disease_ner is False:
            logger.warning("[BioBERT-NER] Skipping NER - models not loaded")
            self.recognized_entities = {'chemicals': set(), 'diseases': set()}
            return

        # Combine all paper text (abstracts + full text if available)
        all_text_by_paper = []
        for paper in self.papers_analyzed:
            abstract = paper.get('abstract_sections', {})
            text_parts = []

            # Add abstract sections
            for section_text in abstract.values():
                if section_text and len(section_text) > 20:
                    text_parts.append(section_text)

            # Add full text if available (prioritize Methods and Results)
            full_text = paper.get('full_text_sections', {})
            if full_text.get('methods'):
                text_parts.append(full_text['methods'][:1500])
            if full_text.get('results'):
                text_parts.append(full_text['results'][:1500])

            combined_text = ' '.join(text_parts)[:5000]  # Limit to 5000 chars per paper

            if combined_text.strip():
                all_text_by_paper.append({
                    'pmid': paper['pmid'],
                    'text': combined_text
                })

        # Extract entities using BioBERT NER
        all_entities = {
            'chemicals': set(),
            'diseases': set()
        }

        def is_valid_entity(entity_text: str) -> bool:
            """Validate that entity is a clean medical term, not a sentence fragment."""
            # Too short (single letters or 2-letter words are usually not real entities)
            if len(entity_text) < 3:
                return False

            # Too long (likely a sentence fragment)
            if len(entity_text) > 50:
                return False

            # Contains too many special characters (sentence fragments)
            special_char_count = sum(1 for c in entity_text if c in '.,:;!?()[]{}#%')
            if special_char_count > 2:
                return False

            # Contains sentence markers or word fragments
            if any(marker in entity_text for marker in ['. ', '##', '( ', ' )', ': ', '; ']):
                return False

            # Contains too many spaces (likely a phrase, not a term)
            if entity_text.count(' ') > 3:
                return False

            # Contains numbers mixed with text in weird ways (e.g., "2, 335 patients")
            import re
            if re.search(r'\d+[,\s]+\d+', entity_text):
                return False

            return True

        for paper_data in all_text_by_paper:
            text = paper_data['text']
            pmid = paper_data['pmid']

            try:
                # Extract chemicals (biomarkers, etc.)
                chemical_entities = self.chemical_ner(text)
                for entity in chemical_entities:
                    if entity['score'] > 0.85:  # High confidence only
                        entity_text = entity['word'].strip()
                        if is_valid_entity(entity_text):
                            all_entities['chemicals'].add(entity_text)

                # Extract diseases
                disease_entities = self.disease_ner(text)
                for entity in disease_entities:
                    if entity['score'] > 0.85:
                        entity_text = entity['word'].strip()
                        if is_valid_entity(entity_text):
                            all_entities['diseases'].add(entity_text)

                logger.debug(f"[BioBERT-NER] PMID:{pmid} - Found {len(chemical_entities)} chemicals, {len(disease_entities)} diseases")

            except Exception as e:
                logger.warning(f"[BioBERT-NER] Failed to process PMID:{pmid} - {e}")
                continue

        logger.info(f"[BioBERT-NER] Total extracted: {len(all_entities['chemicals'])} unique chemicals, "
                    f"{len(all_entities['diseases'])} unique diseases")

        # Store for later use in standardization
        self.recognized_entities = all_entities
        return all_entities

    def _standardize_variable_names(self):
        """
        Standardize variable names using BioBERT NER recognized entities.

        Merges duplicates like:
        - "CRP", "C-reactive protein", "hsCRP" → "CRP"
        - "Type 2 diabetes", "T2DM", "diabetes mellitus type 2" → "Type 2 Diabetes"

        Returns:
            Deduplicated list of variables
        """
        logger.info("[STANDARDIZE] Deduplicating variables using BioBERT NER entities")

        # Build mapping of variable names to canonical names
        canonical_mapping = {}
        all_recognized = list(self.recognized_entities.get('chemicals', set())) + \
                        list(self.recognized_entities.get('diseases', set()))

        # Helper function to find best match
        def find_canonical_name(var_name: str) -> str:
            """Find canonical name for a variable using NER entities."""
            var_lower = var_name.lower()

            # Skip very short variable names (likely nonsensical)
            if len(var_name) < 3:
                return var_name

            # First try exact match
            for entity in all_recognized:
                if entity.lower() == var_lower:
                    return entity

            # Try word-level token matching for better accuracy
            import re
            var_tokens = set(re.findall(r'\b\w+\b', var_lower))

            matches = []
            for entity in all_recognized:
                entity_lower = entity.lower()

                # Skip very short entities for substring matching (prevent "in" matching "CRP")
                if len(entity) < 3:
                    continue

                # Check if entity is a word token in the variable name (not substring)
                entity_tokens = set(re.findall(r'\b\w+\b', entity_lower))

                # Calculate token overlap
                overlap = var_tokens & entity_tokens
                if overlap:
                    # At least one full word matches
                    overlap_ratio = len(overlap) / max(len(var_tokens), len(entity_tokens))
                    if overlap_ratio > 0.5:  # At least 50% token overlap
                        matches.append((entity, overlap_ratio, len(entity)))

                # Also check for meaningful substring matches (at least 5 chars)
                elif len(entity) >= 5 and len(var_name) >= 5:
                    if entity_lower in var_lower:
                        matches.append((entity, 0.8, len(entity)))
                    elif var_lower in entity_lower:
                        matches.append((entity, 0.7, len(entity)))

            if matches:
                # Sort by: 1) overlap ratio (descending), 2) length (ascending - prefer shorter)
                matches.sort(key=lambda x: (-x[1], x[2]))
                return matches[0][0]

            # No match found - keep original name
            return var_name

        # Deduplicate variables
        deduplicated = {}

        for var in self.variables_discovered + self.confounders:
            var_name = var['name']
            canonical_name = find_canonical_name(var_name)

            if canonical_name not in deduplicated:
                # First occurrence - use this variable
                deduplicated[canonical_name] = var.copy()
                deduplicated[canonical_name]['name'] = canonical_name
                canonical_mapping[var_name] = canonical_name
            else:
                # Duplicate found - merge data
                existing = deduplicated[canonical_name]

                # Merge citations
                existing_citations = set(existing.get('citations', []))
                new_citations = set(var.get('citations', []))
                existing['citations'] = list(existing_citations | new_citations)

                # Update range if new data has better info
                if var.get('range') and var['range'].get('mean') is not None:
                    if not existing.get('range') or existing['range'].get('mean') is None:
                        existing['range'] = var['range']

                # Update distribution if new data is more specific
                if var.get('distribution') and var['distribution'] != 'unknown':
                    if not existing.get('distribution') or existing['distribution'] == 'unknown':
                        existing['distribution'] = var['distribution']

                canonical_mapping[var_name] = canonical_name

        logger.info(f"[STANDARDIZE] Reduced {len(self.variables_discovered) + len(self.confounders)} variables "
                   f"to {len(deduplicated)} unique variables")

        # Log deduplication mappings
        if canonical_mapping:
            unique_mappings = {}
            for orig, canon in canonical_mapping.items():
                if canon not in unique_mappings:
                    unique_mappings[canon] = []
                if orig != canon:
                    unique_mappings[canon].append(orig)

            for canon, variants in unique_mappings.items():
                if variants:
                    logger.info(f"[STANDARDIZE] '{canon}' ← {variants}")

        # Split back into variables and confounders
        self.variables_discovered = [v for v in deduplicated.values() if v['role'] != 'confounder']
        self.confounders = [v for v in deduplicated.values() if v['role'] == 'confounder']

        return list(deduplicated.values())

    def _filter_non_variables(self):
        """
        Filter out study statistics that aren't actual variables.

        Removes entries like:
        - Hazard ratios (HR)
        - Odds ratios (OR)
        - Relative risks (RR)
        - P-values
        - Confidence intervals

        These are study results, not variables for data generation.
        """
        logger.info("[FILTER] Removing study statistics from variables list")

        # Keywords that indicate study statistics (not variables)
        statistic_keywords = [
            'hazard ratio', 'hr', 'odds ratio', 'or', 'relative risk', 'rr',
            'p-value', 'p value', 'confidence interval', 'ci',
            'effect size', 'correlation coefficient', 'risk ratio',
            'mortality', 'survival', 'incidence', 'prevalence'
        ]

        def is_study_statistic(var: Dict) -> bool:
            """Check if variable is actually a study statistic."""
            name_lower = var['name'].lower()

            # Check name for statistic keywords
            for keyword in statistic_keywords:
                if keyword in name_lower:
                    # Special cases: "all-cause mortality" is often a study outcome, not variable
                    if 'mortality' in keyword or 'survival' in keyword:
                        return True
                    # HR/OR/RR are always statistics
                    if keyword in ['hr', 'or', 'rr', 'p-value', 'ci']:
                        return True

            # Check if the range looks like a ratio/statistic (0-2 range with mean near 1.0)
            range_data = var.get('range')
            if range_data:
                min_val = range_data.get('min')
                max_val = range_data.get('max')
                mean_val = range_data.get('mean')

                # Hazard ratios typically range 0.5-2.0 with mean around 1.0
                if min_val and max_val and mean_val:
                    if 0.3 <= min_val <= 1.0 and 1.0 <= max_val <= 3.0 and 0.7 <= mean_val <= 1.5:
                        # This looks like a ratio
                        return True

            return False

        # Filter variables
        original_count = len(self.variables_discovered)
        filtered_variables = [v for v in self.variables_discovered if not is_study_statistic(v)]
        removed_count = original_count - len(filtered_variables)

        if removed_count > 0:
            logger.info(f"[FILTER] Removed {removed_count} study statistics:")
            for var in self.variables_discovered:
                if is_study_statistic(var):
                    logger.info(f"  - {var['name']} (role: {var['role']})")

        self.variables_discovered = filtered_variables

        # Also filter confounders
        original_confounders = len(self.confounders)
        self.confounders = [v for v in self.confounders if not is_study_statistic(v)]
        removed_confounders = original_confounders - len(self.confounders)

        if removed_confounders > 0:
            logger.info(f"[FILTER] Removed {removed_confounders} confounders that were study statistics")

        logger.info(f"[FILTER] After filtering: {len(self.variables_discovered)} variables, "
                   f"{len(self.confounders)} confounders")

    async def _expand_search_strategy(self, current_strategy: Dict) -> Dict:
        """Expand search if we need more variables."""

        # Get variables we already have
        current_vars = [v['name'] for v in self.variables_discovered]

        prompt = f"""We're searching for variables related to this hypothesis:
<hypothesis>{self.hypothesis}</hypothesis>

<current_search>
  <query>{current_strategy['query']}</query>
  <variables_found>{len(current_vars)}</variables_found>
  <variable_list>{', '.join(current_vars)}</variable_list>
</current_search>

We need more variables. Think step-by-step:
1. What variable types are we missing?
2. Should we broaden or narrow the search?
3. What related terms should we add?

Return ONLY this XML structure:
<expanded_strategy>
  <query>updated PubMed search query with different terms</query>
  <reasoning>why this will find different/more relevant papers</reasoning>
  <expected_additions>
    <addition>new variable type 1</addition>
    <addition>new variable type 2</addition>
  </expected_additions>
</expanded_strategy>"""

        response = await self.anthropic.messages.create(
            model=self.claude_model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        expanded_xml = self._extract_xml(response.content[0].text, "expanded_strategy")

        expanded_strategy = {
            "query": expanded_xml.findtext("./query", current_strategy['query']),
            "reasoning": expanded_xml.findtext("./reasoning", ""),
            "expected_additions": [a.text for a in expanded_xml.findall("./expected_additions/addition") if a.text]
        }

        self._log_decision(
            "Expanded search strategy",
            expanded_strategy['reasoning'],
            {"new_query": expanded_strategy['query']}
        )

        return expanded_strategy

    async def _synthesize_findings(self) -> Dict[str, Any]:
        """Synthesize all findings with Claude."""

        prompt = f"""You analyzed {len(self.papers_analyzed)} papers for this hypothesis:
<hypothesis>{self.hypothesis}</hypothesis>

<findings>
  <papers_analyzed>{len(self.papers_analyzed)}</papers_analyzed>
  <variables_discovered>{len(self.variables_discovered)}</variables_discovered>
  <confounders_identified>{len(self.confounders)}</confounders_identified>
</findings>

Create a synthesis:
1. What are the key relationships discovered?
2. Which variables are most important?
3. Are there contradictions across papers?
4. What novel insights emerge?

Return ONLY this XML structure:
<synthesis>
  <reasoning_chain>step-by-step synthesis of all findings across papers</reasoning_chain>
  <key_relationships>
    <relationship>relationship 1</relationship>
    <relationship>relationship 2</relationship>
  </key_relationships>
  <novel_insights>
    <insight>insight 1</insight>
    <insight>insight 2</insight>
  </novel_insights>
  <confidence>high</confidence>
</synthesis>"""

        response = await self.anthropic.messages.create(
            model=self.claude_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        synthesis_xml = self._extract_xml(response.content[0].text, "synthesis")

        synthesis = {
            "reasoning_chain": synthesis_xml.findtext("./reasoning_chain", ""),
            "key_relationships": [r.text for r in synthesis_xml.findall("./key_relationships/relationship") if r.text],
            "novel_insights": [i.text for i in synthesis_xml.findall("./novel_insights/insight") if i.text],
            "confidence": synthesis_xml.findtext("./confidence", "medium")
        }

        return synthesis

    def _extract_xml(self, text: str, root_tag: str = "response") -> ET.Element:
        """Extract XML from Claude response (handles markdown code blocks)."""
        text = text.strip()

        # Remove markdown code blocks
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:-1]) if len(lines) > 2 else text
            text = text.replace('```xml', '').replace('```', '').strip()

        # Find XML content
        start_tag = f"<{root_tag}>"
        end_tag = f"</{root_tag}>"

        start_idx = text.find(start_tag)
        end_idx = text.find(end_tag)

        if start_idx != -1 and end_idx != -1:
            xml_text = text[start_idx:end_idx + len(end_tag)]
        else:
            xml_text = text

        try:
            return ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            logger.error(f"Text: {text[:500]}")
            # Return empty element
            return ET.Element(root_tag)

    def _build_synthesis_input(self, hypothesis: str) -> Dict[str, Any]:
        """
        Build synthesis_input: minimal data for synthesis generator.

        Returns dict with variables, correlations, and hypothesis for generator.
        """
        # Extract unique variables (deduplicate by name)
        unique_vars = {}
        for var in self.variables_discovered + self.confounders:
            name = var['name']
            if name not in unique_vars:
                unique_vars[name] = {
                    "name": name,
                    "type": var['type'],
                    "distribution": var.get('distribution', 'unknown'),
                    "range": var.get('range'),
                    "units": var.get('units')
                }

        # Build correlations from relationships
        correlations = []
        for rel in self.relationships:
            correlations.append({
                "var1": rel.get('var1'),
                "var2": rel.get('var2'),
                "correlation": rel.get('effect_size', 0.0)
            })

        return {
            "variables": list(unique_vars.values()),
            "correlations": correlations,
            "hypothesis": hypothesis,
            "source": "literature_discovery"
        }

    def _build_literature_display(
        self,
        hypothesis: str,
        iterations: int,
        synthesis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build literature_display: full metadata for frontend display.

        Returns dict with all paper metadata, abstracts, full text, citations.
        """
        papers = []
        for paper in self.papers_analyzed:
            # Format abstract sections
            abstract_sections = paper.get('abstract_sections', {})
            abstract_display = {
                "background": abstract_sections.get('background'),
                "methods": abstract_sections.get('methods'),
                "results": abstract_sections.get('results'),
                "conclusions": abstract_sections.get('conclusions')
            }

            # Format full text sections (if available)
            full_text_sections = paper.get('full_text_sections', {})
            full_text_display = None
            if full_text_sections:
                full_text_display = {
                    "introduction": full_text_sections.get('introduction'),
                    "methods": full_text_sections.get('methods'),
                    "results": full_text_sections.get('results'),
                    "discussion": full_text_sections.get('discussion'),
                    "conclusions": full_text_sections.get('conclusions')
                }

            # Build PubMed and PMC links
            pmid = paper['pmid']
            pmc_id = paper.get('pmc_id')

            pubmed_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            pmc_link = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/" if pmc_id else None
            doi_link = f"https://doi.org/{paper['doi']}" if paper.get('doi') else None

            papers.append({
                "pmid": pmid,
                "doi": paper.get('doi'),
                "title": paper.get('title', ''),
                "authors": paper.get('authors', []),
                "journal": paper.get('journal', ''),
                "year": paper.get('year', ''),
                "keywords": paper.get('keywords', []),
                "publication_types": paper.get('publication_types', []),
                "abstract": abstract_display,
                "full_text": full_text_display,
                "pubmed_link": pubmed_link,
                "pmc_link": pmc_link,
                "doi_link": doi_link,
                "variables_extracted": paper.get('variables_extracted', []),
                "relevance": paper.get('analysis', {}).get('relevance', 'medium'),
                "key_findings": paper.get('analysis', {}).get('key_findings', '')
            })

        return {
            "hypothesis": hypothesis,
            "papers": papers,
            "total_papers_analyzed": len(self.papers_analyzed),
            "variables_found": len(set(v['name'] for v in self.variables_discovered)),
            "confounders_found": len(set(v['name'] for v in self.confounders)),
            "search_iterations": iterations,
            "synthesis": {
                "reasoning": synthesis.get('reasoning_chain', ''),
                "key_relationships": synthesis.get('key_relationships', []),
                "novel_insights": synthesis.get('novel_insights', []),
                "confidence": synthesis.get('confidence', 'medium')
            }
        }
