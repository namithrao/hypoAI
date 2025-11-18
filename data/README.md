# NHANES Data Processing & Analysis

This directory contains tools for downloading, processing, and analyzing NHANES (National Health and Nutrition Examination Survey) data.

## Available Notebooks

1. **[nhanes_data_download.ipynb](nhanes_data_download.ipynb)** - Download and convert NHANES data
2. **[nhanes_variable_embeddings.ipynb](nhanes_variable_embeddings.ipynb)** - Visualize variables in 3D semantic space

## Quick Start

### 1. Install Dependencies

```bash
cd data
pip install -r requirements.txt
```

### 2. Run Jupyter Notebook

```bash
jupyter notebook nhanes_data_download.ipynb
```

### 3. Execute All Cells

Run all cells in the notebook to:
- Download all NHANES 2017-2018 data files (Demographics, Examination, Laboratory, Questionnaire, Dietary)
- Convert XPT files to Parquet format for efficient storage
- Create variable-level Parquet files for flexible data loading
- Generate visualizations of key variables

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

The [nhanes_variable_embeddings.ipynb](nhanes_variable_embeddings.ipynb) notebook creates interactive 3D visualizations of all NHANES 2017-2018 variables in semantic space.

### What it does:
- Queries all ~2000-3000 NHANES 2017-2018 variables across all categories
- Encodes with 2 BioBERT models (Base + Chemical NER)
- Reduces to 3D using UMAP and t-SNE
- Creates 5 interactive Plotly visualizations
- Performs clustering analysis (KMeans + DBSCAN)
- Supports search, filter, and variable highlighting

### Output:
```
nhanes_embeddings/
├── nhanes_variables_2017_2018.csv       # All variables with metadata
├── embeddings_base_biobert.npy          # Base BioBERT embeddings
├── embeddings_chemical_biobert.npy      # Chemical BioBERT embeddings
├── coords_*.csv                          # 3D coordinates (4 files)
├── clusters.csv                          # Cluster assignments
├── viz_*.html                            # Interactive visualizations (5 files)
└── summary_report.txt                    # Analysis summary
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
