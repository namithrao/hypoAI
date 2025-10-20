# SynthAI Multi-Database Research Architecture

## Vision
AI-powered medical research system that searches across **all publicly available medical databases**, uses **literature analysis** to discover relevant variables, and **synthesizes data** from multiple sources to test hypotheses.

## Multi-Agent Collaborative System

```
User Hypothesis
      ↓
┌─────────────────────────────────────────────────────┐
│           Main Orchestrator Agent                    │
│  (Claude 3.5 Sonnet - coordinates all subagents)   │
└─────────────────────────────────────────────────────┘
      ↓
      ├──→ [1] Literature Analysis Agent
      │         • PubMed MCP Tool
      │         • Extracts: relevant variables, biomarkers,
      │           outcomes, population criteria
      │         • Shares findings with Data Discovery Agent
      │
      ├──→ [2] Data Discovery Agent
      │         • NHANES MCP Tool
      │         • MIMIC-IV MCP Tool
      │         • UK Biobank MCP Tool
      │         • ClinicalTrials.gov MCP Tool
      │         • PhenX Toolkit MCP Tool
      │         • Receives variable suggestions from Literature Agent
      │         • Searches all databases for relevant data
      │
      ├──→ [3] Data Integration Agent
      │         • Harmonizes data from multiple sources
      │         • Handles different formats (XPT, CSV, SQL)
      │         • Creates unified dataset
      │
      └──→ [4] Statistical Analysis Agent
                • Runs hypothesis tests
                • Generates visualizations
                • Interprets results
```

## Medical Databases to Integrate (MCP Tools)

### 1. **NHANES** (Already built, needs fixing)
- **What**: US population health survey
- **Data**: Demographics, lab results, physical exams, nutrition
- **API**: Direct CDC downloads (XPT files)
- **Issue**: Search not finding femur DXA data (DXXFEM_F)
- **Fix**: Improve search terms, expand to examination category

### 2. **PubMed / PubMed Central** (Priority)
- **What**: 35M+ biomedical research articles
- **Data**: Research findings, clinical trial results, methodology
- **API**: NCBI E-utilities API (free)
- **Usage**: Literature Agent extracts relevant variables from papers
- **Example**: For femur fracture query, finds papers mentioning:
  - Time to weight bearing
  - Dual vs lateral plating outcomes
  - Relevant biomarkers (bone density, healing time)

### 3. **MIMIC-IV** (Clinical Outcomes)
- **What**: ICU patient data from Beth Israel Deaconess
- **Data**: Clinical notes, procedures, medications, outcomes
- **API**: BigQuery public dataset (requires auth)
- **Usage**: Surgical outcomes, treatment comparisons
- **Relevance**: Could have orthopedic surgery outcomes

### 4. **ClinicalTrials.gov**
- **What**: 400K+ registered clinical trials
- **Data**: Trial results, endpoints, populations, interventions
- **API**: ClinicalTrials.gov API (free)
- **Usage**: Find trials comparing surgical approaches
- **Example**: Dual plate vs lateral plate femur fracture trials

### 5. **UK Biobank** (Population + Genetics)
- **What**: 500K+ participants with genetic + imaging data
- **Data**: Genetics, MRI/DXA scans, health outcomes
- **API**: Requires approved access
- **Usage**: Genetic risk factors, bone density imaging

### 6. **PhenX Toolkit**
- **What**: Standard measures for phenotypic research
- **Data**: Standardized variable definitions
- **API**: REST API
- **Usage**: Variable harmonization across databases

### 7. **openFDA** (Adverse Events)
- **What**: FDA adverse event reports
- **Data**: Drug/device adverse events
- **API**: openFDA API (free)
- **Usage**: Device failures, complications

### 8. **SEER** (Cancer Outcomes)
- **What**: Cancer registry data
- **Data**: Cancer incidence, treatment, survival
- **API**: SEER*Stat database
- **Usage**: Oncology research

## Example: Distal Femur Fracture Query

**User Query:**
> "In patients with distal femur fractures, does a dual plate approach or a lateral plate approach lead to faster time to weight bearing and better outcomes overall?"

### Agent Workflow:

**1. Literature Agent (PubMed MCP)**
```
Search: "distal femur fracture dual plate lateral plate outcomes"
Finds papers mentioning:
  - Time to weight bearing (primary outcome)
  - Union rate, nonunion rate
  - Complication rate
  - Bone density as predictor
  - Patient age, BMI as confounders
```

**2. Data Discovery Agent**

**NHANES Search:**
```
Variables from literature: bone_density, age, BMI, femur_measurements
Search examination category + "femur" + "bone"
Finds: DXXFEM_F (Dual Energy X-ray Absorptiometry - Femur)
  - BMD (bone mineral density)
  - BMC (bone mineral content)
  - Femoral neck, trochanter measurements
```

**ClinicalTrials.gov Search:**
```
Search: "distal femur fracture" + "plate"
Finds trials comparing:
  - Dual plate vs single lateral plate
  - Time to weight bearing outcomes
  - Union rates
```

**MIMIC-IV Search:**
```
Query procedures: "femur fracture" + "ORIF" + "plate"
Extract: surgical approach, complications, length of stay
```

**3. Integration Agent**
```
Combine:
  - NHANES: Population bone density norms
  - ClinicalTrials: Treatment comparison outcomes
  - MIMIC-IV: Real-world surgical complications
  - PubMed: Meta-analysis of existing evidence
```

**4. Analysis Agent**
```
Statistical tests on combined dataset
Visualizations
Confidence intervals
Limitations assessment
```

## Implementation Priority

### Phase 1: Fix NHANES Search
- [ ] Debug why DXXFEM_F not found
- [ ] Improve search algorithm to check all categories
- [ ] Add fuzzy matching for file descriptions

### Phase 2: Build PubMed MCP Tool
- [ ] Implement NCBI E-utilities wrapper
- [ ] Extract relevant variables from abstracts
- [ ] Share findings with Data Discovery Agent

### Phase 3: Multi-Agent Communication
- [ ] Design agent-to-agent messaging protocol
- [ ] Literature Agent → Data Discovery Agent variable sharing
- [ ] Shared working memory for all agents

### Phase 4: Additional Databases
- [ ] ClinicalTrials.gov MCP tool
- [ ] MIMIC-IV MCP tool (requires credentials)
- [ ] UK Biobank MCP tool (requires approved access)

## Technical Architecture

### MCP Server Structure
```
apps/mcp-tools/
├── nhanes/          # Population health (already built)
├── pubmed/          # Literature search (NEW)
├── clinicaltrials/  # Clinical trial results (NEW)
├── mimic/           # Clinical outcomes (NEW)
├── ukbiobank/       # Genetic + imaging (NEW)
└── shared/          # Common utilities
    ├── variable-harmonizer.ts
    └── data-fetcher.ts
```

### Agent Communication Protocol
```python
class AgentMessage:
    from_agent: str
    to_agent: str
    message_type: str  # "variable_suggestion", "data_found", "query"
    payload: dict

# Example: Literature Agent → Data Discovery Agent
{
    "from_agent": "literature_analyzer",
    "to_agent": "data_discovery",
    "message_type": "variable_suggestion",
    "payload": {
        "variables": ["bone_mineral_density", "time_to_weight_bearing"],
        "source_papers": ["PMID:12345678"],
        "reasoning": "Papers show BMD predicts fracture healing"
    }
}
```

## Database Access Requirements

| Database | Authentication | Cost | Rate Limits |
|----------|---------------|------|-------------|
| NHANES | None | Free | None |
| PubMed | API key (free) | Free | 10 req/sec |
| ClinicalTrials.gov | None | Free | Reasonable use |
| MIMIC-IV | Credentialed access | Free (research) | BigQuery quotas |
| UK Biobank | Approved application | £££ | Project-specific |
| openFDA | None | Free | 240 req/min |

## Next Steps

1. **Immediate**: Fix NHANES search to find DXXFEM_F
2. **Short-term**: Build PubMed MCP tool + Literature Agent
3. **Medium-term**: Build ClinicalTrials.gov MCP tool
4. **Long-term**: Apply for MIMIC-IV and UK Biobank access
