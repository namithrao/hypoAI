# SynthAI MVP Architecture

## Overview

SynthAI MVP uses a **2-stage pipeline** for hypothesis-driven synthetic data generation:

1. **Stage 1: Literature Discovery** - Extract variables from research papers
2. **Stage 2: Synthetic Data Generation** - Generate grounded synthetic datasets

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           USER INPUT                                 │
│                                                                       │
│  "Does elevated CRP predict cardiovascular events in diabetes?"     │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: LITERATURE DISCOVERY                     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │   Literature Discovery Agent V2                             │    │
│  │                                                              │    │
│  │   ┌─────────────────┐    ┌──────────────┐                 │    │
│  │   │  Claude 3.5     │───▶│  BlueBERT    │                 │    │
│  │   │  Sonnet         │    │  Medical NER │                 │    │
│  │   │  (CoT Reasoning)│    └──────────────┘                 │    │
│  │   └─────────────────┘                                      │    │
│  │           │                                                 │    │
│  │           ▼                                                 │    │
│  │   ┌─────────────────┐                                      │    │
│  │   │  MCP Client     │                                      │    │
│  │   │  (PubMed/NCBI)  │                                      │    │
│  │   └─────────────────┘                                      │    │
│  │           │                                                 │    │
│  │           ▼                                                 │    │
│  │   ┌─────────────────────────────────────┐                 │    │
│  │   │  Iterative Search Loop               │                 │    │
│  │   │  • Search PubMed                     │                 │    │
│  │   │  • Analyze papers (Claude)           │                 │    │
│  │   │  • Extract entities (BlueBERT)        │                 │    │
│  │   │  • Expand if < 10 variables          │                 │    │
│  │   │  • Follow citations                  │                 │    │
│  │   └─────────────────────────────────────┘                 │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│                            OUTPUT ▼                                  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │              JSON Schema Output                             │    │
│  │  {                                                          │    │
│  │    "variables": [                                           │    │
│  │      {                                                      │    │
│  │        "name": "CRP",                                       │    │
│  │        "type": "continuous",                                │    │
│  │        "role": "predictor",                                 │    │
│  │        "distribution": "lognormal",                         │    │
│  │        "typical_range": {"min": 0.1, "max": 10, ...},      │    │
│  │        "citations": ["PMID:123"],                           │    │
│  │        "relationship": "positive"                           │    │
│  │      }, ...                                                 │    │
│  │    ],                                                       │    │
│  │    "confounders": [...],                                    │    │
│  │    "relationships": [...],                                  │    │
│  │    "reasoning_chain": "..."                                 │    │
│  │  }                                                          │    │
│  └────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ JSON Handoff
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                STAGE 2: SYNTHETIC DATA GENERATION                    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │   Synthesis Model (TabDDPM or CTGAN)                        │    │
│  │                                                              │    │
│  │   Pre-trained on:                                           │    │
│  │   • NHANES (demographics, labs, outcomes)                   │    │
│  │   • PhysioNet (physiological signals)                       │    │
│  │   • SEER (cancer registry)                                  │    │
│  │   • UK Biobank (large cohort data)                          │    │
│  │   • MIMIC-IV (clinical EHR data)                            │    │
│  │                                                              │    │
│  │   Input: JSON schema from Stage 1                           │    │
│  │   Output: Synthetic dataset matching specifications         │    │
│  │                                                              │    │
│  │   ┌─────────────────────────────────────┐                  │    │
│  │   │  Generation Process                  │                  │    │
│  │   │  1. Parse variable specifications    │                  │    │
│  │   │  2. Sample from learned distributions│                  │    │
│  │   │  3. Apply correlation constraints    │                  │    │
│  │   │  4. Validate statistical properties  │                  │    │
│  │   └─────────────────────────────────────┘                  │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│                            OUTPUT ▼                                  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │         Synthetic Dataset (CSV/Parquet)                     │    │
│  │                                                              │    │
│  │  CRP   | age | BMI | diabetes_duration | cvd_events | ...  │    │
│  │  -------|-----|-----|------------------|------------|------ │    │
│  │  2.3   | 62  | 28  | 5                | 0          | ...   │    │
│  │  5.1   | 58  | 32  | 8                | 1          | ...   │    │
│  │  1.8   | 55  | 26  | 3                | 0          | ...   │    │
│  │  ...   | ... | ... | ...              | ...        | ...   │    │
│  │                                                              │    │
│  │  (N=10,000 rows, grounded in real data patterns)            │    │
│  └────────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
                      ┌──────────────────┐
                      │  Statistical     │
                      │  Analysis        │
                      │  (Future: Stage3)│
                      └──────────────────┘
```

## Week 1 Progress Summary

### ✅ Completed Tasks

1. **Environment Setup** (8 hrs)
   - Installed PyTorch 2.2.0, Transformers 4.38.0
   - Upgraded Anthropic SDK to 0.72.0
   - Configured BlueBERT model (bionlp/bluebert_pubmed_mimic_uncased_L-12_H-768_A-12)
   - Files created:
     - [requirements.txt](apps/backend/requirements.txt)
     - [test_setup.py](apps/backend/test_setup.py)

2. **Literature Discovery Agent V2** (12 hrs)
   - Implemented single-agent architecture (removed multi-agent orchestrator)
   - Integrated Claude 3.5 Sonnet for CoT reasoning
   - Added BlueBERT for medical NER (lazy loading)
   - Implemented iterative search loop (continues until ≥10 variables)
   - Files created:
     - [literature_discovery_agent_v2.py](apps/backend/synthai_backend/agents/literature_discovery_agent_v2.py)
     - [test_literature_agent.py](apps/backend/test_literature_agent.py)
     - Updated [__init__.py](apps/backend/synthai_backend/agents/__init__.py)

3. **JSON Schema Design** (8 hrs)
   - Created comprehensive JSON Schema for Literature Agent output
   - Defined variable structure (name, type, role, distribution, citations)
   - Defined relationship structure (correlations, effect sizes)
   - Created Pydantic models for validation
   - Files created:
     - [literature_discovery_output.json](apps/backend/schemas/literature_discovery_output.json)
     - [literature_models.py](apps/backend/synthai_backend/models/literature_models.py)

4. **Architecture Documentation** (4 hrs)
   - Documented 2-stage pipeline architecture
   - Created ASCII diagrams showing data flow
   - Defined component responsibilities
   - File created:
     - [ARCHITECTURE_MVP.md](ARCHITECTURE_MVP.md)

### 📊 Total Time: ~32 hours of 78-hour Week 1 plan

### ⏳ Remaining Tasks

**Literature Agent Enhancement** (16 hrs remaining):
- Test BlueBERT NER on sample medical text
- Enhance PubMed MCP integration
- Build complete CoT reasoning prompts
- Test full integration with valid API key

**Synthesis Model Preparation** (30 hrs):
- Download NHANES data
- Download PhysioNet data
- Download SEER data
- Build preprocessing pipelines
- Evaluate TabDDPM vs CTGAN

---

## Component Details

### Stage 1: Literature Discovery Agent

**Technology Stack:**
- **Claude 3.5 Sonnet** (claude-3-5-sonnet-20240620)
  - Chain-of-thought reasoning
  - Paper analysis and synthesis
  - Relationship discovery
- **BlueBERT** (bionlp/bluebert_pubmed_mimic_uncased_L-12_H-768_A-12)
  - Medical named entity recognition
  - Text embeddings for similarity
- **MCP (Model Context Protocol)**
  - NCBI E-utilities client
  - PubMed search and fetch

**Key Features:**
1. **Iterative Search**: Continues until ≥10 variables discovered
2. **Citation Tracking**: All variables linked to PMIDs
3. **Relationship Discovery**: Identifies correlations, confounders, mediators
4. **CoT Reasoning**: Complex multi-step analysis of literature

**Output Format:** JSON Schema ([schema](apps/backend/schemas/literature_discovery_output.json))

**Current Status:** ✅ Structure complete, needs API key for full testing

### Stage 2: Synthesis Model

**Technology Stack:**
- **TabDDPM** (Tabular Denoising Diffusion Probabilistic Models)
  - Diffusion-based generation
  - Better for complex distributions
- **CTGAN** (Conditional Tabular GAN)
  - GAN-based generation
  - Faster inference
  - Good for categorical variables

**Pre-training Data (to be downloaded):**
- NHANES: 50,000+ participants, 500+ variables
- PhysioNet: 10M+ physiological signals
- SEER: Cancer registry (millions of records)
- UK Biobank: 500,000+ participants
- MIMIC-IV: 200,000+ ICU admissions

**Current Status:** ⏳ Pending - Week 1 remaining tasks

---

## File Structure

```
synthai_backend/
├── agents/
│   ├── __init__.py                         # ✅ Updated
│   ├── literature_discovery_agent_v2.py    # ✅ New MVP implementation
│   ├── literature_agent.py                 # (Legacy - to remove)
│   ├── dataset_discovery_agent.py          # (Legacy - to remove)
│   └── orchestrator.py                     # (Legacy - to remove)
│
├── models/
│   ├── __init__.py
│   ├── models.py                           # API models
│   └── literature_models.py                # ✅ New Pydantic models
│
├── synthesis/                               # ⏳ To be implemented
│   ├── __init__.py
│   ├── tabddpm.py
│   └── ctgan.py
│
└── schemas/
    └── literature_discovery_output.json    # ✅ New JSON Schema

tests/
├── test_setup.py                           # ✅ New
└── test_literature_agent.py                # ✅ New
```

---

## Technology Choices Rationale

| Component | Technology | Why? |
|-----------|-----------|------|
| Reasoning Model | Claude 3.5 Sonnet | Best-in-class CoT reasoning, strong medical knowledge |
| Medical NER | BlueBERT | Specialized on PubMed abstracts + MIMIC clinical text |
| Literature Access | MCP + NCBI | Standardized protocol, reliable PubMed access |
| Synthesis Model | TabDDPM/CTGAN | State-of-art for tabular synthetic data generation |
| Pre-training Data | NHANES, PhysioNet, SEER, UK Biobank, MIMIC-IV | Large-scale, publicly available, high-quality medical data |
| Schema Format | JSON Schema + Pydantic | Standardized, validated, type-safe, interoperable |

---

## Next Steps (Week 1 Remaining)

### Immediate (Next Session)
1. **Get valid Anthropic API key** for testing Literature Agent
2. **Test BlueBERT NER** on sample medical abstracts
3. **Start NHANES data download** (~8 hours)

### This Week
4. Download PhysioNet data (8 hours)
5. Download SEER data (8 hours)
6. Build preprocessing pipeline (4 hours)
7. Evaluate TabDDPM vs CTGAN (4 hours)

### Week 2-3
- Train synthesis models on downloaded data
- Integrate Literature Agent with Synthesis Model
- End-to-end testing

---

**Version**: MVP Week 1 (Day 1 Complete)
**Last Updated**: 2025-11-02
**Status**: 32/78 hours completed (41%)
