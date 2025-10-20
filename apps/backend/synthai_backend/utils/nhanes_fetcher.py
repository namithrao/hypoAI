"""
NHANES Data Fetcher - Direct downloads from CDC

Replaces nhanes-pytool-api with direct CDC downloads using MCP-provided URLs.
"""

import logging
import os
from pathlib import Path
from typing import Optional
import pandas as pd
import requests

logger = logging.getLogger(__name__)


class NHANESFetcher:
    """
    Fetch NHANES XPT data files directly from CDC.

    Uses MCP server to get download URLs, then downloads and parses XPT files.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize NHANES fetcher.

        Args:
            cache_dir: Directory to cache downloaded XPT files.
                      Defaults to ~/.synthai/nhanes_cache
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.synthai/nhanes_cache")

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"NHANES cache directory: {self.cache_dir}")

    def download_xpt(
        self,
        download_url: str,
        file_code: str,
        cycle: str,
        force_download: bool = False
    ) -> Path:
        """
        Download XPT file from CDC.

        Args:
            download_url: Full CDC download URL
            file_code: NHANES file code (e.g., "BMX_D")
            cycle: NHANES cycle (e.g., "2005-2006")
            force_download: If True, re-download even if cached

        Returns:
            Path to downloaded XPT file

        Raises:
            requests.HTTPError: If download fails
        """
        # Cache file path: cache_dir/2005-2006_BMX_D.XPT
        cache_filename = f"{cycle}_{file_code}.XPT"
        cache_path = self.cache_dir / cache_filename

        # Use cached file if exists and not forcing re-download
        if cache_path.exists() and not force_download:
            logger.info(f"Using cached file: {cache_path}")
            return cache_path

        # Download file
        logger.info(f"Downloading {download_url}")
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        # Save to cache
        with open(cache_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded to: {cache_path} ({cache_path.stat().st_size} bytes)")
        return cache_path

    def load_xpt(self, xpt_path: Path) -> pd.DataFrame:
        """
        Load XPT file into pandas DataFrame.

        Args:
            xpt_path: Path to XPT file

        Returns:
            DataFrame with XPT data

        Raises:
            ValueError: If XPT file cannot be parsed
        """
        try:
            logger.info(f"Loading XPT file: {xpt_path}")
            df = pd.read_sas(xpt_path, format='xport', encoding='utf-8')
            logger.info(f"Loaded DataFrame: {df.shape[0]} rows × {df.shape[1]} columns")
            return df
        except Exception as e:
            raise ValueError(f"Failed to load XPT file {xpt_path}: {e}")

    def fetch_data(
        self,
        download_url: str,
        file_code: str,
        cycle: str,
        force_download: bool = False
    ) -> pd.DataFrame:
        """
        Download and load NHANES data in one step.

        Args:
            download_url: Full CDC download URL
            file_code: NHANES file code (e.g., "BMX_D")
            cycle: NHANES cycle (e.g., "2005-2006")
            force_download: If True, re-download even if cached

        Returns:
            DataFrame with NHANES data
        """
        xpt_path = self.download_xpt(download_url, file_code, cycle, force_download)
        return self.load_xpt(xpt_path)

    def clear_cache(self, cycle: Optional[str] = None) -> int:
        """
        Clear cached XPT files.

        Args:
            cycle: If specified, only clear files for this cycle.
                  If None, clear all cached files.

        Returns:
            Number of files deleted
        """
        count = 0

        if cycle:
            # Clear specific cycle
            pattern = f"{cycle}_*.XPT"
            for file_path in self.cache_dir.glob(pattern):
                file_path.unlink()
                count += 1
                logger.info(f"Deleted cached file: {file_path}")
        else:
            # Clear all XPT files
            for file_path in self.cache_dir.glob("*.XPT"):
                file_path.unlink()
                count += 1
                logger.info(f"Deleted cached file: {file_path}")

        logger.info(f"Cleared {count} cached files")
        return count
