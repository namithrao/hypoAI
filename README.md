# SynthAI

AI research companion for medical data retrieval, synthesis, and hypothesis testing.

## Overview

SynthAI is a production-ready MVP that enables medical researchers to:

1. **Ask natural language research questions** and receive programmatically assembled datasets
2. **Retrieve data from public sources** (NHANES, SEER, PhysioNet) with intelligent query planning
3. **Generate synthetic data** using advanced techniques (UMAP, VAE) with user-controlled parameters
4. **Get explainable statistical results** with publication-ready reports and next-step guidance

## Architecture

```
├── apps/
│   ├── frontend/         # React + Vite + Tailwind UI
│   ├── backend/          # FastAPI + analysis + synthesis
│   └── mcp-tools/        # TypeScript MCP data retrieval tools
│       ├── nhanes/       # NHANES data access
│       ├── seer/         # SEER cancer registry API
│       └── physionet/    # PhysioNet open datasets
├── packages/
│   ├── python-mcp/       # Python MCP client library
│   ├── schemas/          # Shared OpenAPI/JSON schemas
│   └── nhanes-dict/      # NHANES variable dictionary
├── infra/
│   ├── docker/           # Container configurations
│   └── scripts/          # Setup and demo scripts
└── tests/                # Comprehensive test suite
```

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.9+
- Docker & Docker Compose

### Development Setup

1. **Clone and install dependencies:**
```bash
git clone <repository-url>
cd SynthAI
npm install
```

2. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your API keys (SEER_API_KEY, GRETEL_API_KEY optional)
```

3. **Start development environment:**
```bash
npm run dev
# This runs: docker-compose up
```

4. **Access the application:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Core Features

### 🔍 Intelligent Data Retrieval
- **Natural Language Queries**: "Does elevated CRP predict cardiovascular events in adults 40-65?"
- **Smart Source Selection**: AI ranks and selects optimal data sources
- **Multi-source Integration**: Seamlessly combines NHANES, SEER, PhysioNet data

### 🧬 Advanced Synthetic Data Generation
- **Multiple Engines**: SDV/CTGAN (open source) + Gretel (managed, optional)
- **Dimensionality Reduction**: UMAP for intelligent data projection
- **VAE Generation**: Variational autoencoders for realistic synthetic samples
- **User Controls**: Sliders for sample size, noise, distributions, correlations

### 📊 Explainable Statistical Analysis
- **Multiple Models**: Logistic regression, survival analysis, Bayesian inference
- **Feature Attribution**: SHAP explanations for model decisions
- **Publication Ready**: HTML→PDF reports with embedded plots
- **Next Steps**: Automated guidance for additional data collection

### 🔒 Security & Provenance
- **Full Traceability**: SHA-256 content hashing, audit logs
- **Reproducibility**: Export/import run configurations
- **Privacy**: No PII storage beyond user uploads
- **Governance**: License tracking, data source attribution

## API Reference

### MCP Tools

Each tool implements the JSON-RPC over stdio protocol:

```typescript
// NHANES data retrieval
nhanes.get({
  cycles: ["2017-2018", "2019-2020"],
  columns: ["SEQN", "LBXCRP", "RIAGENDR"],
  where: { "RIDAGEYR": [40, 65] },
  limit: 10000,
  dry_run: false
})

// SEER cancer registry
seer.query({
  endpoint: "incidence",
  params: { site: "breast", year: "2020" },
  limit: 5000
})

// PhysioNet datasets
physionet.catalog({ query: "ECG", limit: 50 })
physionet.fetch({
  dataset: "mitdb",
  files: ["100.dat"],
  columns: ["time", "signal"]
})
```

### Backend API

```python
# Smart data selection
POST /api/v1/research/query
{
  "question": "Does elevated CRP predict cardiovascular events?",
  "user_data": "optional_csv_base64",
  "constraints": {
    "age_range": [40, 65],
    "sample_size_min": 1000
  }
}

# Synthetic data generation
POST /api/v1/synthesis/generate
{
  "dataset_id": "uuid",
  "config": {
    "sample_size": 20000,
    "noise": 0.03,
    "method": "vae",
    "distributions": {"CRP": "lognormal", "BMI": "normal"}
  }
}

# Statistical analysis
POST /api/v1/analysis/run
{
  "dataset_id": "uuid",
  "outcome": "cvd_events",
  "exposures": ["CRP", "BMI"],
  "models": ["logistic", "survival"]
}
```

## Environment Variables

```bash
# Required
DATA_DIR=/app/data

# Optional - External APIs
SEER_API_KEY=your_seer_key
GRETEL_API_KEY=your_gretel_key  # For managed synthetic data
OPENAI_API_KEY=your_openai_key  # For query parsing

# Optional - Configuration
FRONTEND_PORT=3000
BACKEND_PORT=8000
DATABASE_URL=sqlite:///synthai.db
LOG_LEVEL=INFO
```

## Testing

```bash
# Run all tests
npm test

# Individual components
npm test --workspace=apps/backend
npm test --workspace=apps/mcp-tools/nhanes

# Integration tests
npm run test:integration

# End-to-end demo
python scripts/demo_run.py
```

## Demo Workflow

The included demo script demonstrates a complete research workflow:

```bash
python scripts/demo_run.py
```

This will:
1. Query: "Does elevated CRP predict 1-year cardiovascular events in adults 40–65?"
2. Fetch relevant NHANES variables (CRP, age, sex, BMI, smoking status)
3. Generate synthetic augmentation (20k samples, 3% noise, realistic correlations)
4. Train logistic regression + gradient boosting models
5. Output explainable PDF report with SHAP feature attributions

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Ensure all tests pass: `npm test`
5. Commit with conventional commits: `git commit -m "feat: add amazing feature"`
6. Push and create a Pull Request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- NHANES, SEER, and PhysioNet for providing open access to critical health datasets
- The open source community for statistical and ML libraries
- Research community for driving evidence-based medicine forward