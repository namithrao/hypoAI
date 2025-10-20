"""
Multi-source NHANES variable metadata fetcher.
Combines HTML scraping, REST API, and PyTool API for comprehensive discovery.
Zero hardcoded knowledge - all data fetched dynamically.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlencode

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from nhanes_data.nhanes_data_api import NHANESDataAPI

logger = logging.getLogger(__name__)


class VariableMetadata:
    """Represents NHANES variable metadata from any source."""

    def __init__(
        self,
        variable_name: str,
        variable_description: str,
        data_file_name: str,
        data_file_description: str,
        component: str,
        begin_year: str,
        end_year: str,
        source: str,  # 'html_scraper', 'api', 'pytool'
        unit: Optional[str] = None
    ):
        self.variable_name = variable_name
        self.variable_description = variable_description
        self.data_file_name = data_file_name
        self.data_file_description = data_file_description
        self.component = component
        self.begin_year = begin_year
        self.end_year = end_year
        self.source = source
        self.unit = unit or self._extract_unit_from_description(variable_description)

    def _extract_unit_from_description(self, description: str) -> Optional[str]:
        """Extract unit from description like 'CRP (mg/L)' → 'mg/L'"""
        # Match last parenthetical that looks like a unit
        unit_pattern = r'\(([^)]*(?:mg|g|dL|L|mmol|μmol|%|years?|cm|kg|m²)[^)]*)\)\s*$'
        match = re.search(unit_pattern, description, re.IGNORECASE)
        return match.group(1) if match else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'variable_name': self.variable_name,
            'variable_description': self.variable_description,
            'data_file_name': self.data_file_name,
            'data_file_description': self.data_file_description,
            'component': self.component,
            'begin_year': self.begin_year,
            'end_year': self.end_year,
            'source': self.source,
            'unit': self.unit
        }


class MetadataCache:
    """TTL-based cache for variable metadata."""

    def __init__(self, ttl_seconds: int = 86400):  # 24 hours default
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self.cache:
            timestamp, value = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                logger.debug(f"Cache hit: {key}")
                return value
            else:
                logger.debug(f"Cache expired: {key}")
                del self.cache[key]
        return None

    def set(self, key: str, value: Any):
        """Set cache value with current timestamp."""
        self.cache[key] = (time.time(), value)
        logger.debug(f"Cache set: {key}")

    def _make_key(self, **kwargs) -> str:
        """Generate cache key from parameters."""
        key_str = json.dumps(kwargs, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()


class NHANESMetadataFetcher:
    """
    Multi-source NHANES variable metadata fetcher.

    Sources (in priority order):
    1. HTML Scraper - Scrapes variable list from NHANES website
    2. REST API - Uses NHANES search API (if available)
    3. PyTool API - Falls back to PyTool library
    """

    # NHANES website URLs
    VARIABLE_LIST_URL = "https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx"
    SEARCH_API_URL = "https://wwwn.cdc.gov/nchs/nhanes/search/DataPage.aspx"

    def __init__(self, nhanes_api: NHANESDataAPI, cache_ttl: int = 86400):
        self.nhanes_api = nhanes_api
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.cache = MetadataCache(ttl_seconds=cache_ttl)

    async def fetch_all_sources(
        self,
        cycle: str,
        component: str,
        search_term: Optional[str] = None
    ) -> List[VariableMetadata]:
        """
        Fetch variable metadata from ALL sources and merge results.

        Args:
            cycle: NHANES cycle (e.g., "2017-2018")
            component: Data category (e.g., "laboratory")
            search_term: Optional search term to filter variables

        Returns:
            Merged list of VariableMetadata from all sources
        """
        cache_key = self.cache._make_key(
            cycle=cycle, component=component, search_term=search_term or ""
        )

        # Check cache
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Fetch from all sources in parallel
        results = await asyncio.gather(
            self._fetch_from_html_scraper(cycle, component, search_term),
            self._fetch_from_api(cycle, component, search_term),
            self._fetch_from_pytool(cycle, component),
            return_exceptions=True
        )

        # Merge results
        all_metadata = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                source_name = ["HTML", "API", "PyTool"][i]
                logger.warning(f"{source_name} source failed: {result}")
            else:
                all_metadata.extend(result)

        # Deduplicate by variable_name (prefer html_scraper > api > pytool)
        seen = {}
        unique_metadata = []
        priority = {'html_scraper': 3, 'api': 2, 'pytool': 1}

        for meta in all_metadata:
            if meta.variable_name not in seen:
                seen[meta.variable_name] = meta
                unique_metadata.append(meta)
            else:
                # Replace if higher priority source
                existing = seen[meta.variable_name]
                if priority.get(meta.source, 0) > priority.get(existing.source, 0):
                    unique_metadata.remove(existing)
                    seen[meta.variable_name] = meta
                    unique_metadata.append(meta)

        logger.info(
            f"Fetched {len(unique_metadata)} unique variables from {len(all_metadata)} total "
            f"({cycle}/{component})"
        )

        # Cache results
        self.cache.set(cache_key, unique_metadata)

        return unique_metadata

    async def _fetch_from_html_scraper(
        self,
        cycle: str,
        component: str,
        search_term: Optional[str]
    ) -> List[VariableMetadata]:
        """
        Source A: Scrape NHANES variable list HTML table.
        """
        logger.debug(f"Fetching from HTML scraper: {cycle}/{component}")

        try:
            begin_year, end_year = cycle.split("-")

            # Build query parameters
            params = {
                "Component": component.capitalize(),
                "BeginYear": begin_year,
                "EndYear": end_year
            }

            if search_term:
                params["SearchTerms"] = search_term

            url = f"{self.VARIABLE_LIST_URL}?{urlencode(params)}"

            # Fetch HTML
            response = await self.http_client.get(url)
            response.raise_for_status()

            # Parse HTML table
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the variable list table (usually first table with id='GridView1')
            table = soup.find('table', {'id': 'GridView1'})
            if not table:
                # Try finding any table
                table = soup.find('table')

            if not table:
                logger.debug("No table found in HTML")
                return []

            # Parse table rows
            metadata_list = []
            rows = table.find_all('tr')[1:]  # Skip header row

            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    metadata = VariableMetadata(
                        variable_name=cols[0].get_text(strip=True),
                        variable_description=cols[1].get_text(strip=True),
                        data_file_name=cols[2].get_text(strip=True),
                        data_file_description=cols[3].get_text(strip=True),
                        component=cols[6].get_text(strip=True),
                        begin_year=cols[4].get_text(strip=True),
                        end_year=cols[5].get_text(strip=True),
                        source='html_scraper'
                    )
                    metadata_list.append(metadata)

            logger.debug(f"HTML scraper: Found {len(metadata_list)} variables")
            return metadata_list

        except Exception as e:
            logger.debug(f"HTML scraper failed: {e}")
            return []

    async def _fetch_from_api(
        self,
        cycle: str,
        component: str,
        search_term: Optional[str]
    ) -> List[VariableMetadata]:
        """
        Source B: Use NHANES REST API (if available).
        """
        logger.debug(f"Fetching from REST API: {cycle}/{component}")

        try:
            begin_year, end_year = cycle.split("-")

            # Try NHANES search API
            params = {
                "Component": component.capitalize(),
                "BeginYear": begin_year,
                "EndYear": end_year,
                "format": "json"  # Request JSON response
            }

            if search_term:
                params["SearchTerms"] = search_term

            response = await self.http_client.get(
                self.SEARCH_API_URL,
                params=params,
                headers={"Accept": "application/json"}
            )

            # Try parsing as JSON
            try:
                data = response.json()

                # Parse API response (structure may vary)
                metadata_list = []

                # Attempt to find variable data in response
                # Common keys: 'results', 'data', 'variables'
                variables_data = (
                    data.get('results') or
                    data.get('data') or
                    data.get('variables') or
                    []
                )

                for var in variables_data:
                    metadata = VariableMetadata(
                        variable_name=var.get('VariableName', ''),
                        variable_description=var.get('VariableDescription', ''),
                        data_file_name=var.get('DataFileName', ''),
                        data_file_description=var.get('DataFileDescription', ''),
                        component=var.get('Component', component),
                        begin_year=var.get('BeginYear', begin_year),
                        end_year=var.get('EndYear', end_year),
                        source='api'
                    )
                    metadata_list.append(metadata)

                logger.debug(f"REST API: Found {len(metadata_list)} variables")
                return metadata_list

            except json.JSONDecodeError:
                # API might not support JSON
                logger.debug("API response is not JSON")
                return []

        except Exception as e:
            logger.debug(f"REST API failed: {e}")
            return []

    async def _fetch_from_pytool(
        self,
        cycle: str,
        component: str
    ) -> List[VariableMetadata]:
        """
        Source C: Use NHANES PyTool API to infer variable metadata.

        PyTool doesn't expose variable descriptions directly,
        but we can get file names and then inspect DataFrames.
        """
        logger.debug(f"Fetching from PyTool: {cycle}/{component}")

        try:
            # Get file names for this category/cycle
            file_names = self.nhanes_api.list_file_names(component, [cycle])

            metadata_list = []

            # For each file, load data to get variable names
            for file_name in file_names[:10]:  # Limit to first 10 files to avoid slowness
                try:
                    df = self.nhanes_api.retrieve_data(
                        data_category=component,
                        cycle=cycle,
                        filename=file_name,
                        include_uncommon_variables=True
                    )

                    # Get cycle-specific file name
                    cycle_mapping = self.nhanes_api.retrieve_cycle_data_file_name_mapping(
                        component, file_name
                    )
                    data_file_name = cycle_mapping.get(cycle, file_name)

                    begin_year, end_year = cycle.split("-")

                    # Create metadata for each column
                    for col in df.columns:
                        if col != 'SEQN':  # Skip sequence number
                            metadata = VariableMetadata(
                                variable_name=col,
                                variable_description=col,  # No description from PyTool
                                data_file_name=data_file_name,
                                data_file_description=file_name,
                                component=component,
                                begin_year=begin_year,
                                end_year=end_year,
                                source='pytool'
                            )
                            metadata_list.append(metadata)

                except Exception as e:
                    logger.debug(f"Failed to load file {file_name}: {e}")
                    continue

            logger.debug(f"PyTool: Found {len(metadata_list)} variables")
            return metadata_list

        except Exception as e:
            logger.debug(f"PyTool failed: {e}")
            return []

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
