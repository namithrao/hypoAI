# NHANES Data Processing & Analysis

This directory contains tools for downloading, processing, and analyzing NHANES (National Health and Nutrition Examination Survey) data.

## Available Tools

### Scripts
1. **[nhanes_data_loader_all_years.py](nhanes_data_loader_all_years.py)** - Download and merge NHANES data from all years
   - Downloads data for all cycles (1999-2000 through 2017-2018+)
   - Merges all components (Demographics, Dietary, Examination, Laboratory, Questionnaire) by SEQN
   - Exports to CSV
   - Optional Google Drive upload
   - See [NHANES_DATA_LOADER_GUIDE.md](NHANES_DATA_LOADER_GUIDE.md) for detailed usage

2. **[simple_nhanes_fetcher.py](simple_nhanes_fetcher.py)** - Fetch NHANES variable metadata
   - Retrieves variable lists and descriptions from CDC website
   - Does not download actual data (only metadata)
   - Used by notebooks for variable exploration

### Notebooks
1. **[nhanes_embedding_simple.ipynb](nhanes_embedding_simple.ipynb)** - BioBERT embeddings & visualization
   - Loads NHANES 2017-2018 variable metadata
   - Encodes with BioBERT (biomedical language model)
   - Creates 2D/3D visualizations with UMAP
   - Semantic search for similar variables

## Quick Start

### Option 1: Download All Years with Data Loader Script (Recommended)

```bash
# 1. Install dependencies
cd data
pip install -r requirements.txt

# 2. Download and merge all NHANES cycles
python nhanes_data_loader_all_years.py --output-dir ./nhanes_output --cycles all

# 3. Or download specific years only
python nhanes_data_loader_all_years.py --output-dir ./nhanes_output --cycles "2017-2018,2015-2016"
```

**Output:** Merged CSV files in `nhanes_output/` directory, one per cycle, with all components joined by SEQN.

See [NHANES_DATA_LOADER_GUIDE.md](NHANES_DATA_LOADER_GUIDE.md) for complete documentation.

### Option 2: Explore Variables with BioBERT Embeddings

```bash
# 1. Install dependencies (if not already done)
pip install -r requirements.txt

# 2. Launch Jupyter
jupyter notebook nhanes_embedding_simple.ipynb

# 3. Run all cells to:
# - Fetch NHANES 2017-2018 variable metadata
# - Encode with BioBERT
# - Visualize in 2D/3D semantic space
# - Search for similar variables
```

## What the Notebook Does

### Data Download
- Downloads all NHANES 2017-2018 data files from CDC website
- Categories included:
  - **Demographics** (1 file): Age, gender, race, sample weights
  - **Examination** (8 files): Body measures, blood pressure, vision, oral health, audiometry
  - **Laboratory** (17 files): Blood chemistry, CRP, cholesterol, glucose, vitamins, CBC, thyroid
  - **Questionnaire** (16 files): Health history, lifestyle, diet, medications, alcohol, smoking
  - **Dietary** (5 files): Nutrient intake, food items, supplements

### Data Processing
- Converts XPT (SAS transport) files to Parquet format
- Creates two Parquet storage options:
  1. **Full datasets**: One Parquet file per NHANES data file
  2. **Variable-level**: Each variable saved as separate Parquet file (for large datasets)

### Data Visualization
- CRP distribution
- CRP by age group
- Age and gender distributions
- Saves visualization as PNG

## Output Structure

```
nhanes_2017_2018/
├── xpt/                          # Original XPT files from CDC
│   ├── demographics/
│   ├── examination/
│   ├── laboratory/
│   ├── questionnaire/
│   └── dietary/
├── parquet/                      # Full dataset Parquet files
│   ├── demographics/
│   ├── examination/
│   ├── laboratory/
│   ├── questionnaire/
│   └── dietary/
└── parquet_by_variable/          # Variable-level Parquet files
    ├── dietary/
    │   └── DR1TOT_J/
    │       ├── metadata.json     # Dataset metadata
    │       ├── SEQN.parquet      # Unique identifier
    │       ├── DR1TKCAL.parquet  # Total kcal variable
    │       └── ...               # Other variables
    ├── questionnaire/
    └── laboratory/
```

## Loading Data Examples

### Load Full Dataset
```python
import pandas as pd

# Load complete CRP dataset
crp_df = pd.read_parquet('nhanes_2017_2018/parquet/laboratory/HSCRP_J.parquet')
print(crp_df.head())
```

### Load Single Variable
```python
# Load only CRP values (smaller memory footprint)
crp_only = pd.read_parquet('nhanes_2017_2018/parquet_by_variable/laboratory/HSCRP_J/LBXHSCRP.parquet')
print(crp_only.head())
```

### Merge Multiple Datasets
```python
# Load demographics and CRP
demo = pd.read_parquet('nhanes_2017_2018/parquet/demographics/DEMO_J.parquet')
crp = pd.read_parquet('nhanes_2017_2018/parquet/laboratory/HSCRP_J.parquet')

# Merge on SEQN (unique identifier)
merged = demo.merge(crp, on='SEQN', how='inner')
print(f"Merged dataset: {len(merged)} rows")
```

## NHANES Variable Naming

All NHANES variables follow consistent naming:
- **SEQN**: Unique respondent identifier (used for merging)
- **Prefix indicates data type**:
  - `RIA*`: Demographics/admin
  - `BMX*`: Body measures
  - `BPX*`: Blood pressure
  - `LBX*`: Laboratory values
  - `DR1*`: Dietary day 1
  - `DR2*`: Dietary day 2
  - etc.

## Key Variables

### Demographics (DEMO_J)
- `SEQN`: Unique ID
- `RIDAGEYR`: Age in years
- `RIAGENDR`: Gender (1=Male, 2=Female)
- `RIDRETH3`: Race/ethnicity
- `WTMEC2YR`: Sample weight

### Laboratory - CRP (HSCRP_J)
- `SEQN`: Unique ID
- `LBXHSCRP`: High-sensitivity CRP (mg/L)

### Laboratory - Glucose (GLU_J)
- `LBXGLU`: Fasting glucose (mg/dL)

### Laboratory - Cholesterol (TCHOL_J, HDL_J, TRIGLY_J)
- `LBXTC`: Total cholesterol (mg/dL)
- `LBDHDD`: HDL cholesterol (mg/dL)
- `LBXTR`: Triglycerides (mg/dL)

## Benefits of Parquet Format

- **Faster loading**: 10-100x faster than XPT
- **Smaller size**: 50-80% smaller than XPT (with compression)
- **Column selection**: Load only needed columns
- **Type preservation**: Maintains data types
- **Wide compatibility**: Works with Pandas, Polars, DuckDB, Spark

## Notes

- Total download size: ~200-500 MB
- Processing time: ~5-10 minutes (depends on internet speed)
- NHANES uses SEQN as the unique identifier for merging datasets
- Some variables have missing values (coded as NaN)
- Sample weights (e.g., WTMEC2YR) should be used for population-level estimates

## Variable Embedding Visualization

The [nhanes_embedding_simple.ipynb](nhanes_embedding_simple.ipynb) notebook creates interactive 2D/3D visualizations of all NHANES 2017-2018 variables in semantic space.

### What it does:
- Fetches all ~2000-3000 NHANES 2017-2018 variables across all categories
- Encodes variable descriptions with BioBERT (biomedical language model)
- Reduces to 2D/3D using UMAP for visualization
- Creates interactive Plotly visualizations
- Enables semantic search for similar variables

### Output:
```
data/
├── nhanes_2017_2018_embeddings.npy              # BioBERT embeddings (768-dim)
├── nhanes_2017_2018_variables_with_coords.csv   # Variables + 2D/3D coordinates
├── nhanes_2017_2018_variables_3d.html           # Interactive 3D visualization
└── nhanes_2017_2018_variables_2d.html           # Interactive 2D visualization
```

### Use Cases:
- **Semantic Search**: Find variables similar to a concept (e.g., "cholesterol")
- **Variable Recommendation**: Suggest related variables for hypothesis testing
- **Data Quality**: Identify duplicate or redundant variables
- **Synthetic Data**: Guide variable selection for generation
- **Documentation**: Auto-generate variable groupings

### Example Usage:
```python
# Load embeddings for semantic search
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

embeddings = np.load('nhanes_embeddings/embeddings_base_biobert.npy')
df = pd.read_csv('nhanes_embeddings/nhanes_variables_2017_2018.csv')

# Find variables similar to "CRP"
query_idx = df[df['variable_name'] == 'LBXHSCRP'].index[0]
similarities = cosine_similarity([embeddings[query_idx]], embeddings)[0]
similar_idx = np.argsort(similarities)[::-1][1:11]
print("Variables similar to CRP:")
print(df.iloc[similar_idx][['variable_name', 'variable_description']])
```

## References

- [NHANES Website](https://www.cdc.gov/nchs/nhanes/index.htm)
- [NHANES 2017-2018 Data](https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?BeginYear=2017)
- [NHANES Tutorials](https://wwwn.cdc.gov/nchs/nhanes/tutorials/default.aspx)
- [BioBERT Paper](https://arxiv.org/abs/1901.08746)
- [UMAP Documentation](https://umap-learn.readthedocs.io/)
