# NHANES MCP Tool

Model Context Protocol (MCP) tool for retrieving NHANES (National Health and Nutrition Examination Survey) data.

## Overview

This tool provides programmatic access to NHANES data through a standardized MCP interface. It supports:

- **Cycle Selection**: Query specific NHANES cycles (e.g., "2017-2018", "2019-2020")
- **Column Projection**: Select specific variables to retrieve
- **Filtering**: Apply conditions on numeric and categorical variables
- **Pagination**: Handle large datasets with limit/offset
- **Dry Run**: Estimate result sizes without fetching data
- **Provenance Tracking**: Full traceability of data sources and transformations

## Installation

```bash
npm install
npm run build
```

## Usage

### As MCP Server

```bash
# Start the MCP server
npm start

# Or in development mode
npm run dev
```

### As Library

```typescript
import { NhanesClient } from '@synthai/mcp-nhanes';

const client = new NhanesClient('./data/nhanes');

// Get CRP and demographics for adults 40-65
const result = await client.get({
  cycles: ['2019-2020'],
  columns: ['SEQN', 'LBXCRP', 'RIAGENDR', 'RIDAGEYR', 'BMXBMI'],
  where: {
    RIDAGEYR: [40, 65],  // Age range
    RIAGENDR: [1, 2]     // Both genders
  },
  limit: 1000
});

console.log(`Retrieved ${result.actual_rows} rows`);
console.log(`Columns: ${result.columns.join(', ')}`);
```

## API Reference

### nhanes.get

Retrieve NHANES data with optional filtering and pagination.

#### Parameters

- **cycles** (string[]): NHANES cycles to query
  - Format: "YYYY-YYYY" (e.g., "2017-2018", "2019-2020")
  - Default: All available cycles

- **columns** (string[]): Specific variables to retrieve
  - Examples: ["SEQN", "LBXCRP", "RIAGENDR", "RIDAGEYR", "BMXBMI"]
  - Default: All available columns

- **where** (object): Filter conditions
  - **Equality**: `{ "RIAGENDR": 1 }`
  - **Range Array**: `{ "RIDAGEYR": [40, 65] }`
  - **Range Object**: `{ "RIDAGEYR": { "min": 40, "max": 65 } }`
  - **In Array**: `{ "RIAGENDR": [1, 2] }`

- **limit** (number): Maximum rows to return (default: 10,000)

- **offset** (number): Rows to skip for pagination (default: 0)

- **dry_run** (boolean): Return only metadata and estimates (default: false)

#### Response

```typescript
{
  data?: Record<string, unknown>[];     // Actual data (unless dry_run)
  estimated_rows?: number;              // Estimated rows (dry_run only)
  actual_rows?: number;                 // Actual rows returned
  provenance: {
    source: "NHANES";
    dataset: string;                    // File names used
    version: string;                    // NHANES version
    date: string;                       // Data release date
    license: string;                    // Data license
    request_params: NhanesQuery;        // Original request
    request_timestamp: string;          // Request time
    sha256_hash?: string;               // Data content hash
  };
  columns: string[];                    // Column names
  errors?: string[];                    // Error messages
  warnings?: string[];                  // Warning messages
}
```

## Example Queries

### Basic Demographics

```typescript
await client.get({
  cycles: ['2019-2020'],
  columns: ['SEQN', 'RIAGENDR', 'RIDAGEYR'],
  limit: 100
});
```

### Inflammatory Markers for Adults

```typescript
await client.get({
  cycles: ['2017-2018', '2019-2020'],
  columns: ['SEQN', 'LBXCRP', 'RIAGENDR', 'RIDAGEYR'],
  where: {
    RIDAGEYR: [18, 80],
    LBXCRP: { max: 10 }  // Filter outliers
  },
  limit: 5000
});
```

### Dry Run for Large Queries

```typescript
const estimate = await client.get({
  cycles: ['2019-2020'],
  columns: ['SEQN', 'LBXCRP', 'BMXBMI'],
  where: {
    RIDAGEYR: [40, 65]
  },
  dry_run: true
});

console.log(`Estimated rows: ${estimate.estimated_rows}`);
```

### Pagination

```typescript
// Get first page
const page1 = await client.get({
  cycles: ['2019-2020'],
  limit: 1000,
  offset: 0
});

// Get second page
const page2 = await client.get({
  cycles: ['2019-2020'],
  limit: 1000,
  offset: 1000
});
```

## Available Variables

### Demographics (DEMO)
- **SEQN**: Respondent sequence number (required for merging)
- **RIAGENDR**: Gender (1=Male, 2=Female)
- **RIDAGEYR**: Age in years
- **RIDRETH3**: Race/ethnicity

### Laboratory (LAB)
- **LBXCRP**: C-reactive protein (mg/dL)
- **LBXGLU**: Glucose (mg/dL)
- **LBXIN**: Insulin (μU/mL)

### Body Measures (BMX)
- **BMXBMI**: Body Mass Index (kg/m²)
- **BMXWT**: Weight (kg)
- **BMXHT**: Height (cm)

### Blood Pressure (BPX)
- **BPXSY1**: Systolic BP - 1st reading
- **BPXDI1**: Diastolic BP - 1st reading

## Data Sources

This tool accesses NHANES data from the CDC's National Center for Health Statistics:

- **Source**: https://wwwn.cdc.gov/nchs/nhanes/
- **License**: Public Domain (U.S. Government)
- **Cycles**: 2015-2016, 2017-2018, 2019-2020 (more available on request)

## Testing

```bash
# Run unit tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

## Development

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Development mode (watch)
npm run dev

# Lint code
npm run lint
```

## Environment Variables

- **NHANES_CACHE_DIR**: Directory for caching NHANES data files (default: ./data/nhanes)

## Troubleshooting

### Common Issues

1. **Missing Data Files**: The tool generates sample data for demonstration. In production, you would download actual NHANES .XPT files.

2. **Memory Usage**: Large queries may consume significant memory. Use pagination for datasets >10k rows.

3. **Variable Names**: NHANES uses specific variable codes (e.g., LBXCRP for CRP). See the NHANES documentation for complete variable lists.

### Performance Tips

- Use **dry_run** to estimate query sizes before execution
- Apply **filters** early to reduce data processing
- Use **column projection** to minimize memory usage
- Implement **pagination** for large result sets

## License

MIT License - See LICENSE file for details.