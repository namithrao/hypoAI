"""
NHANES Data Loader - All Years
Downloads, merges, and exports NHANES data for all available cycles.

This script:
1. Downloads NHANES data from all cycles (1999-2000 through 2017-2018+)
2. For each cycle, downloads all 5 components (Demographics, Dietary, Examination, Laboratory, Questionnaire)
3. Merges all components within each cycle by SEQN (participant sequence number)
4. Saves merged data as CSV files
5. Optionally uploads to Google Drive

Usage:
    python nhanes_data_loader_all_years.py --output-dir ./nhanes_output --cycles all
    python nhanes_data_loader_all_years.py --output-dir ./nhanes_output --cycles 2017-2018
    python nhanes_data_loader_all_years.py --output-dir ./nhanes_output --upload-to-gdrive
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict
import time

import pandas as pd
import requests
from tqdm import tqdm

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NHANESDataLoader:
    """
    Comprehensive NHANES data loader for all years.
    Downloads, merges, and exports NHANES data.
    """

    # All available NHANES cycles
    ALL_CYCLES = [
        '1999-2000', '2001-2002', '2003-2004', '2005-2006', '2007-2008',
        '2009-2010', '2011-2012', '2013-2014', '2015-2016', '2017-2018'
    ]

    # Data components
    COMPONENTS = ['Demographics', 'Dietary', 'Examination', 'Laboratory', 'Questionnaire']

    # Cycle letter suffixes for file naming
    CYCLE_LETTERS = {
        '1999-2000': '',  # No letter suffix
        '2001-2002': 'B',
        '2003-2004': 'C',
        '2005-2006': 'D',
        '2007-2008': 'E',
        '2009-2010': 'F',
        '2011-2012': 'G',
        '2013-2014': 'H',
        '2015-2016': 'I',
        '2017-2018': 'J',
    }

    def __init__(self, cache_dir: str = "./nhanes_cache", output_dir: str = "./nhanes_output"):
        """
        Initialize NHANES data loader.

        Args:
            cache_dir: Directory to cache downloaded XPT files
            output_dir: Directory to save merged CSV files
        """
        self.cache_dir = Path(cache_dir)
        self.output_dir = Path(output_dir)

        # Create directories
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cache directory: {self.cache_dir}")
        logger.info(f"Output directory: {self.output_dir}")

    def get_file_list_for_cycle(self, cycle: str) -> Dict[str, List[str]]:
        """
        Get list of data files for a specific cycle.

        This uses the CDC website to get the actual file codes for each component.

        Args:
            cycle: NHANES cycle (e.g., "2017-2018")

        Returns:
            Dictionary mapping component to list of file codes
        """
        logger.info(f"Fetching file list for {cycle}")

        begin_year, end_year = cycle.split('-')
        base_url = "https://wwwn.cdc.gov/nchs/nhanes/search/datapage.aspx"

        file_dict = {}

        for component in self.COMPONENTS:
            url = f"{base_url}?Component={component}&CycleBeginYear={begin_year}"

            try:
                # Fetch the HTML page
                tables = pd.read_html(url)

                if not tables:
                    logger.warning(f"No tables found for {component} in {cycle}")
                    file_dict[component] = []
                    continue

                # The first table contains the file list
                df = tables[0]

                # Extract file codes from the "Data File" column
                if 'Data File' in df.columns:
                    file_codes = df['Data File'].dropna().unique().tolist()
                    file_dict[component] = file_codes
                    logger.info(f"  {component}: {len(file_codes)} files")
                else:
                    logger.warning(f"No 'Data File' column for {component}")
                    file_dict[component] = []

            except Exception as e:
                logger.error(f"Error fetching file list for {component}: {e}")
                file_dict[component] = []

            time.sleep(0.5)  # Be nice to CDC servers

        return file_dict

    def download_xpt_file(self, file_code: str, cycle: str, force_download: bool = False) -> Optional[Path]:
        """
        Download a single XPT file from CDC.

        Args:
            file_code: NHANES file code (e.g., "DEMO_J")
            cycle: NHANES cycle (e.g., "2017-2018")
            force_download: If True, re-download even if cached

        Returns:
            Path to downloaded file, or None if download failed
        """
        # Construct CDC download URL
        # Format: https://wwwn.cdc.gov/Nchs/Nhanes/{cycle}/{file_code}.XPT
        cycle_path = cycle.replace('-', '-')  # CDC uses dash format
        download_url = f"https://wwwn.cdc.gov/Nchs/Nhanes/{cycle_path}/{file_code}.XPT"

        # Cache file path
        cache_filename = f"{cycle}_{file_code}.XPT"
        cache_path = self.cache_dir / cache_filename

        # Use cached file if exists
        if cache_path.exists() and not force_download:
            logger.debug(f"Using cached file: {cache_path}")
            return cache_path

        # Download file
        try:
            logger.debug(f"Downloading {download_url}")
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()

            # Save to cache
            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.debug(f"Downloaded: {cache_path} ({cache_path.stat().st_size} bytes)")
            return cache_path

        except Exception as e:
            logger.error(f"Failed to download {file_code}: {e}")
            return None

    def load_xpt_file(self, xpt_path: Path) -> Optional[pd.DataFrame]:
        """
        Load XPT file into pandas DataFrame.

        Args:
            xpt_path: Path to XPT file

        Returns:
            DataFrame with data, or None if loading failed
        """
        try:
            df = pd.read_sas(xpt_path, format='xport', encoding='utf-8')
            logger.debug(f"Loaded {xpt_path.name}: {df.shape[0]} rows × {df.shape[1]} columns")
            return df
        except Exception as e:
            logger.error(f"Failed to load {xpt_path}: {e}")
            return None

    def download_and_load_component(self, component: str, file_codes: List[str], cycle: str) -> List[pd.DataFrame]:
        """
        Download and load all files for a component.

        Args:
            component: Component name (e.g., "Laboratory")
            file_codes: List of file codes to download
            cycle: NHANES cycle

        Returns:
            List of DataFrames for this component
        """
        dataframes = []

        logger.info(f"  Processing {component} ({len(file_codes)} files)")

        for file_code in tqdm(file_codes, desc=f"  {component}", leave=False):
            # Download
            xpt_path = self.download_xpt_file(file_code, cycle)
            if xpt_path is None:
                continue

            # Load
            df = self.load_xpt_file(xpt_path)
            if df is not None:
                dataframes.append(df)

        return dataframes

    def merge_component_files(self, dataframes: List[pd.DataFrame], component: str) -> Optional[pd.DataFrame]:
        """
        Merge multiple files from the same component by SEQN.

        Args:
            dataframes: List of DataFrames to merge
            component: Component name (for logging)

        Returns:
            Merged DataFrame, or None if merge failed
        """
        if not dataframes:
            logger.warning(f"No data to merge for {component}")
            return None

        if len(dataframes) == 1:
            return dataframes[0]

        # Merge all dataframes on SEQN
        try:
            merged = dataframes[0]
            for i, df in enumerate(dataframes[1:], start=1):
                # Outer join to keep all participants
                merged = merged.merge(df, on='SEQN', how='outer', suffixes=('', f'_{i}'))

            logger.info(f"  Merged {len(dataframes)} {component} files: {merged.shape[0]} rows × {merged.shape[1]} columns")
            return merged

        except Exception as e:
            logger.error(f"Failed to merge {component} files: {e}")
            return None

    def merge_all_components(self, component_dfs: Dict[str, pd.DataFrame]) -> Optional[pd.DataFrame]:
        """
        Merge all components (Demographics, Dietary, Examination, Laboratory, Questionnaire) by SEQN.

        Args:
            component_dfs: Dictionary mapping component name to merged DataFrame

        Returns:
            Final merged DataFrame with all components, or None if merge failed
        """
        # Filter out None values
        valid_components = {k: v for k, v in component_dfs.items() if v is not None}

        if not valid_components:
            logger.error("No valid component data to merge")
            return None

        try:
            # Start with Demographics (usually the base)
            if 'Demographics' in valid_components:
                merged = valid_components['Demographics']
                logger.info(f"Starting with Demographics: {merged.shape[0]} rows × {merged.shape[1]} columns")
            else:
                # If no Demographics, start with first available component
                first_component = list(valid_components.keys())[0]
                merged = valid_components[first_component]
                logger.info(f"Starting with {first_component}: {merged.shape[0]} rows × {merged.shape[1]} columns")
                valid_components.pop(first_component)

            # Merge remaining components
            for component, df in valid_components.items():
                if component == 'Demographics':
                    continue

                logger.info(f"Merging {component}: {df.shape[0]} rows × {df.shape[1]} columns")
                merged = merged.merge(df, on='SEQN', how='outer', suffixes=('', f'_{component}'))

            logger.info(f"Final merged data: {merged.shape[0]} rows × {merged.shape[1]} columns")
            return merged

        except Exception as e:
            logger.error(f"Failed to merge all components: {e}")
            return None

    def process_cycle(self, cycle: str, save_csv: bool = True) -> Optional[pd.DataFrame]:
        """
        Process a complete NHANES cycle: download, merge, and save.

        Args:
            cycle: NHANES cycle (e.g., "2017-2018")
            save_csv: If True, save merged data as CSV

        Returns:
            Merged DataFrame for this cycle, or None if processing failed
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing NHANES cycle: {cycle}")
        logger.info(f"{'='*80}")

        # Get file list for this cycle
        file_dict = self.get_file_list_for_cycle(cycle)

        # Download and merge each component
        component_dfs = {}

        for component in self.COMPONENTS:
            file_codes = file_dict.get(component, [])
            if not file_codes:
                logger.warning(f"No files found for {component}")
                continue

            # Download and load all files for this component
            dataframes = self.download_and_load_component(component, file_codes, cycle)

            # Merge files within component
            merged_component = self.merge_component_files(dataframes, component)
            if merged_component is not None:
                component_dfs[component] = merged_component

        # Merge all components
        merged_all = self.merge_all_components(component_dfs)

        if merged_all is None:
            logger.error(f"Failed to process cycle {cycle}")
            return None

        # Save to CSV
        if save_csv:
            csv_path = self.output_dir / f"nhanes_{cycle.replace('-', '_')}_merged.csv"
            logger.info(f"Saving to {csv_path}")
            merged_all.to_csv(csv_path, index=False)
            logger.info(f"Saved: {csv_path} ({csv_path.stat().st_size / 1e6:.2f} MB)")

        return merged_all

    def process_all_cycles(self, cycles: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        """
        Process multiple NHANES cycles.

        Args:
            cycles: List of cycles to process. If None, process all available cycles.

        Returns:
            Dictionary mapping cycle to merged DataFrame
        """
        if cycles is None:
            cycles = self.ALL_CYCLES

        results = {}

        for cycle in cycles:
            try:
                df = self.process_cycle(cycle)
                if df is not None:
                    results[cycle] = df
            except Exception as e:
                logger.error(f"Error processing cycle {cycle}: {e}")
                continue

        logger.info(f"\n{'='*80}")
        logger.info(f"Processing complete!")
        logger.info(f"Successfully processed {len(results)}/{len(cycles)} cycles")
        logger.info(f"{'='*80}\n")

        return results


def upload_to_google_drive(file_path: Path, folder_id: Optional[str] = None):
    """
    Upload a file to Google Drive.

    Args:
        file_path: Path to file to upload
        folder_id: Google Drive folder ID (optional)

    Requires:
        - Google Drive API credentials
        - pydrive or google-api-python-client installed
    """
    try:
        from pydrive.auth import GoogleAuth
        from pydrive.drive import GoogleDrive

        # Authenticate
        gauth = GoogleAuth()
        gauth.LocalWebserverAuth()  # Creates local webserver for authentication
        drive = GoogleDrive(gauth)

        # Upload file
        file_metadata = {'title': file_path.name}
        if folder_id:
            file_metadata['parents'] = [{'id': folder_id}]

        gfile = drive.CreateFile(file_metadata)
        gfile.SetContentFile(str(file_path))
        gfile.Upload()

        logger.info(f"Uploaded to Google Drive: {file_path.name}")
        logger.info(f"File ID: {gfile['id']}")

    except ImportError:
        logger.error("PyDrive not installed. Install with: pip install PyDrive")
        logger.error("Alternatively, install google-api-python-client")
    except Exception as e:
        logger.error(f"Failed to upload to Google Drive: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download and merge NHANES data from all years"
    )

    parser.add_argument(
        '--cycles',
        type=str,
        default='all',
        help='Comma-separated list of cycles (e.g., "2017-2018,2015-2016") or "all" for all cycles'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='./nhanes_output',
        help='Directory to save merged CSV files'
    )

    parser.add_argument(
        '--cache-dir',
        type=str,
        default='./nhanes_cache',
        help='Directory to cache downloaded XPT files'
    )

    parser.add_argument(
        '--upload-to-gdrive',
        action='store_true',
        help='Upload merged CSV files to Google Drive'
    )

    parser.add_argument(
        '--gdrive-folder-id',
        type=str,
        default=None,
        help='Google Drive folder ID for uploads'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse cycles
    if args.cycles.lower() == 'all':
        cycles = None  # Process all
    else:
        cycles = [c.strip() for c in args.cycles.split(',')]

    # Create loader
    loader = NHANESDataLoader(
        cache_dir=args.cache_dir,
        output_dir=args.output_dir
    )

    # Process cycles
    results = loader.process_all_cycles(cycles)

    # Upload to Google Drive if requested
    if args.upload_to_gdrive:
        logger.info("\nUploading to Google Drive...")
        output_dir = Path(args.output_dir)
        for csv_file in output_dir.glob("nhanes_*_merged.csv"):
            upload_to_google_drive(csv_file, args.gdrive_folder_id)

    logger.info("\nDone!")


if __name__ == "__main__":
    main()
