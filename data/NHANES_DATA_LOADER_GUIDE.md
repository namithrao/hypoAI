# NHANES Data Loader - Complete Guide

## Overview

The `nhanes_data_loader_all_years.py` script provides a comprehensive solution for downloading, merging, and exporting NHANES (National Health and Nutrition Examination Survey) data across all available years.

### What It Does

1. **Downloads** NHANES data from CDC for multiple cycles (1999-2000 through 2017-2018+)
2. **Merges** data from all 5 components within each cycle by SEQN (participant ID):
   - Demographics
   - Dietary
   - Examination
   - Laboratory
   - Questionnaire
3. **Exports** merged data as CSV files
4. **Uploads** to Google Drive (optional)

## Quick Start

### 1. Install Dependencies

```bash
cd data
pip install -r requirements.txt
```

### 2. Basic Usage

Download and merge all NHANES cycles:

```bash
python nhanes_data_loader_all_years.py --output-dir ./nhanes_output --cycles all
```

Download specific cycles only:

```bash
python nhanes_data_loader_all_years.py --output-dir ./nhanes_output --cycles "2017-2018,2015-2016"
```

### 3. Output

The script creates merged CSV files in the output directory:

```
nhanes_output/
├── nhanes_1999_2000_merged.csv
├── nhanes_2001_2002_merged.csv
├── nhanes_2003_2004_merged.csv
├── ...
└── nhanes_2017_2018_merged.csv
```

Each CSV contains:
- **SEQN**: Unique participant identifier
- **All variables** from Demographics, Dietary, Examination, Laboratory, and Questionnaire
- Typically **2000-5000 columns** (all NHANES variables for that cycle)
- Typically **8000-10000 rows** (all participants)

## Command-Line Options

```bash
python nhanes_data_loader_all_years.py [OPTIONS]
```

### Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--cycles` | Cycles to download (comma-separated or "all") | `all` | `--cycles "2017-2018,2015-2016"` |
| `--output-dir` | Directory for merged CSV files | `./nhanes_output` | `--output-dir /path/to/output` |
| `--cache-dir` | Directory for cached XPT files | `./nhanes_cache` | `--cache-dir /path/to/cache` |
| `--upload-to-gdrive` | Upload CSV files to Google Drive | `False` | `--upload-to-gdrive` |
| `--gdrive-folder-id` | Google Drive folder ID for uploads | `None` | `--gdrive-folder-id "ABC123XYZ"` |
| `--verbose` | Enable verbose logging | `False` | `--verbose` |

## Examples

### Example 1: Download All Cycles

```bash
python nhanes_data_loader_all_years.py \
  --cycles all \
  --output-dir ./nhanes_all_years \
  --verbose
```

**Output:**
- 10 CSV files (one per cycle)
- Total size: ~2-5 GB
- Time: ~30-60 minutes (depending on internet speed)

### Example 2: Download Recent Cycles Only

```bash
python nhanes_data_loader_all_years.py \
  --cycles "2015-2016,2017-2018" \
  --output-dir ./nhanes_recent
```

**Output:**
- 2 CSV files
- Total size: ~400-800 MB
- Time: ~5-10 minutes

### Example 3: Upload to Google Drive

```bash
python nhanes_data_loader_all_years.py \
  --cycles "2017-2018" \
  --output-dir ./nhanes_2017_2018 \
  --upload-to-gdrive \
  --gdrive-folder-id "YOUR_FOLDER_ID_HERE"
```

**Note:** Requires Google Drive authentication (see below)

## Google Drive Integration

### Setup Google Drive Authentication

1. **Install PyDrive2:**
   ```bash
   pip install PyDrive2
   ```

2. **Create Google API Credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or select existing)
   - Enable Google Drive API
   - Create OAuth 2.0 credentials
   - Download `client_secrets.json`
   - Place in the same directory as the script

3. **First Run Authentication:**
   ```bash
   python nhanes_data_loader_all_years.py \
     --cycles "2017-2018" \
     --upload-to-gdrive
   ```

   - A browser window will open
   - Sign in to Google account
   - Grant permissions
   - Credentials saved for future runs

4. **Upload to Specific Folder:**

   Get the folder ID from Google Drive URL:
   ```
   https://drive.google.com/drive/folders/ABC123XYZ
                                         ^^^^^^^^^ This is the folder ID
   ```

   Then use:
   ```bash
   python nhanes_data_loader_all_years.py \
     --upload-to-gdrive \
     --gdrive-folder-id "ABC123XYZ"
   ```

### Alternative: Manual Upload

If you prefer not to use the automated upload:

1. Run the script without `--upload-to-gdrive`
2. Manually upload CSV files from `output_dir` to Google Drive

## Data Structure

### SEQN: The Key to Merging

All NHANES datasets share a common identifier: **SEQN** (Respondent Sequence Number)

- Unique for each participant within a cycle
- Used to merge data across components
- Always present in every NHANES data file

### How Merging Works

Within each cycle (e.g., 2017-2018):

1. **Demographics** (1 file): Base participant info
   - SEQN, age, gender, race, sample weights

2. **Dietary** (multiple files): Food intake data
   - Merged by SEQN using outer join

3. **Examination** (multiple files): Physical measurements
   - Merged by SEQN using outer join

4. **Laboratory** (multiple files): Lab test results
   - Merged by SEQN using outer join

5. **Questionnaire** (multiple files): Survey responses
   - Merged by SEQN using outer join

6. **Final Merge**: All components combined by SEQN
   - Outer join: keeps all participants
   - Result: One row per participant with all variables

### Example Merged Data Structure

```
SEQN  | RIDAGEYR | RIAGENDR | BMXBMI | LBXGLU | LBXTC | DR1TKCAL | ...
------|----------|----------|--------|--------|-------|----------|----
83732 | 45       | 1        | 28.3   | 95     | 198   | 2100     | ...
83733 | 62       | 2        | 31.2   | 110    | 215   | 1800     | ...
83734 | 28       | 1        | 24.5   | 88     | 175   | 2400     | ...
...
```

**Columns:**
- `SEQN`: Participant ID
- `RIDAGEYR`: Age in years (Demographics)
- `RIAGENDR`: Gender (Demographics)
- `BMXBMI`: BMI (Examination)
- `LBXGLU`: Glucose (Laboratory)
- `LBXTC`: Total cholesterol (Laboratory)
- `DR1TKCAL`: Total calories day 1 (Dietary)
- ... (2000-5000 more columns)

## Loading Merged Data

### Python (Pandas)

```python
import pandas as pd

# Load merged data
df = pd.read_csv('nhanes_output/nhanes_2017_2018_merged.csv')

print(f"Shape: {df.shape}")
print(f"Participants: {df['SEQN'].nunique()}")
print(f"Variables: {len(df.columns)}")

# Example analysis: glucose levels by age group
df['age_group'] = pd.cut(df['RIDAGEYR'], bins=[0, 18, 40, 65, 100])
print(df.groupby('age_group')['LBXGLU'].mean())
```

### R

```r
library(data.table)

# Load merged data
df <- fread('nhanes_output/nhanes_2017_2018_merged.csv')

print(paste("Shape:", nrow(df), "x", ncol(df)))
print(paste("Participants:", length(unique(df$SEQN))))

# Example analysis
summary(df$LBXGLU)
```

## Combining Multiple Cycles

To combine data across multiple years:

```python
import pandas as pd

cycles = ['1999_2000', '2001_2002', '2003_2004', '2005_2006',
          '2007_2008', '2009_2010', '2011_2012', '2013_2014',
          '2015_2016', '2017_2018']

dfs = []
for cycle in cycles:
    df = pd.read_csv(f'nhanes_output/nhanes_{cycle}_merged.csv')
    df['cycle'] = cycle.replace('_', '-')  # Add cycle identifier
    dfs.append(df)

# Combine all cycles
# Note: Different cycles may have different variables
# Use outer join to keep all variables
combined = pd.concat(dfs, ignore_index=True, sort=False)

print(f"Combined data: {combined.shape}")
print(f"Total participants: {len(combined)}")

# Save combined data
combined.to_csv('nhanes_all_cycles_combined.csv', index=False)
```

**Note:** Variables may differ across cycles. Missing values will be NaN.

## Performance and Storage

### Download Times

| Cycles | Files | Download Time | Processing Time | Total |
|--------|-------|---------------|-----------------|-------|
| 1 cycle | ~50 files | 5-10 min | 2-5 min | ~10-15 min |
| All 10 cycles | ~500 files | 50-100 min | 20-50 min | ~90-150 min |

*Times vary based on internet speed and CPU*

### Storage Requirements

| Data | Size |
|------|------|
| XPT cache (1 cycle) | ~200-500 MB |
| XPT cache (all cycles) | ~2-5 GB |
| CSV output (1 cycle) | ~50-150 MB |
| CSV output (all cycles) | ~500 MB - 1.5 GB |

### Recommendations

- **Local Development**: Download 1-2 recent cycles for testing
- **Full Analysis**: Download all cycles to external drive or cloud storage
- **Cloud Processing**: Use Google Colab or AWS with large storage

## Troubleshooting

### Issue: Download Fails

**Error:** `Failed to download XXX.XPT`

**Solutions:**
1. Check internet connection
2. Verify CDC website is accessible
3. Try again later (CDC servers may be temporarily unavailable)
4. Check if file code is correct for that cycle

### Issue: Memory Error

**Error:** `MemoryError` when merging large datasets

**Solutions:**
1. Process one cycle at a time
2. Use a machine with more RAM (>16 GB recommended for all cycles)
3. Use chunked reading:
   ```python
   chunks = pd.read_csv('file.csv', chunksize=10000)
   for chunk in chunks:
       process(chunk)
   ```

### Issue: Google Drive Upload Fails

**Error:** `PyDrive not installed` or authentication errors

**Solutions:**
1. Install PyDrive2: `pip install PyDrive2`
2. Download `client_secrets.json` from Google Cloud Console
3. Place in script directory
4. Delete `credentials.json` and re-authenticate

### Issue: Missing Variables

**Error:** Expected variable not found in merged data

**Reasons:**
1. Variable only available in certain cycles
2. Variable renamed across cycles
3. Component not downloaded

**Solution:**
Check NHANES documentation for variable availability by cycle:
https://wwwn.cdc.gov/nchs/nhanes/

## Advanced Usage

### Use as Python Module

```python
from nhanes_data_loader_all_years import NHANESDataLoader

# Create loader
loader = NHANESDataLoader(
    cache_dir='./cache',
    output_dir='./output'
)

# Process single cycle
df = loader.process_cycle('2017-2018', save_csv=True)

# Process multiple cycles
cycles = ['2015-2016', '2017-2018']
results = loader.process_all_cycles(cycles)

# Access results
for cycle, df in results.items():
    print(f"{cycle}: {df.shape}")
```

### Custom File Selection

To download specific files only (not all components):

```python
# Modify the script to download only specific file codes
file_codes = ['DEMO_J', 'BMXJ', 'LBXGLU_J']  # Example

for file_code in file_codes:
    xpt_path = loader.download_xpt_file(file_code, '2017-2018')
    df = loader.load_xpt_file(xpt_path)
    # Process df...
```

## Related Files

- **simple_nhanes_fetcher.py**: Fetches variable metadata (not actual data)
- **nhanes_embedding_simple.ipynb**: BioBERT embeddings of variable descriptions
- **README.md**: General NHANES data documentation

## References

- [NHANES Website](https://www.cdc.gov/nchs/nhanes/index.htm)
- [NHANES Data Files](https://wwwn.cdc.gov/nchs/nhanes/Default.aspx)
- [NHANES Tutorials](https://wwwn.cdc.gov/nchs/nhanes/tutorials/default.aspx)
- [Variable Search](https://wwwn.cdc.gov/nchs/nhanes/search/)

## Support

For issues or questions:
1. Check this guide
2. Review NHANES documentation
3. Check CDC NHANES FAQ
4. Open GitHub issue in the repository

---

**Last Updated:** November 2025
**Script Version:** 1.0.0
