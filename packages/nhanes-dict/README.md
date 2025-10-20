# NHANES Variable Dictionary

A comprehensive variable dictionary for NHANES (National Health and Nutrition Examination Survey) data, designed to help researchers easily map common research terms to NHANES variable codes.

## Overview

This package provides:

- **Variable Mapping**: Maps common research terms to NHANES variable codes
- **Research Area Templates**: Pre-defined variable sets for common research areas
- **Search Functionality**: Find variables by description, clinical significance, or aliases
- **Data File Information**: Get file names and components for different NHANES cycles

## Installation

```bash
npm install @synthai/nhanes-dict
```

## Basic Usage

```typescript
import { nhanesDict } from '@synthai/nhanes-dict';

// Look up a variable by common name
const crepVariable = nhanesDict.lookupVariable('crp');
console.log(crepVariable?.nhanes_code); // "LBXCRP"

// Get NHANES code directly
const bmiCode = nhanesDict.getVariableCode('bmi');
console.log(bmiCode); // "BMXBMI"

// Get multiple codes at once
const codes = nhanesDict.getVariableCodes(['age', 'sex', 'bmi']);
console.log(codes);
// { age: "RIDAGEYR", sex: "RIAGENDR", bmi: "BMXBMI" }
```

## Research Area Templates

Get pre-defined variable sets for common research areas:

```typescript
// Get variables for cardiovascular research
const cvdVariables = nhanesDict.getResearchVariables('cardiovascular_risk');
console.log(cvdVariables);
// ["age", "sex", "race_ethnicity", "bmi", "systolic_bp", ...]

// Get NHANES codes for a research area
const cvdCodes = nhanesDict.getResearchVariableCodes('cardiovascular_risk');
console.log(cvdCodes);
// { age: "RIDAGEYR", sex: "RIAGENDR", bmi: "BMXBMI", ... }

// Available research areas
const areas = nhanesDict.getResearchAreas();
console.log(areas);
// ["cardiovascular_risk", "metabolic_syndrome", "inflammation", "diabetes_research"]
```

## Search and Discovery

```typescript
// Search variables by text
const diabetesVars = nhanesDict.searchVariables('diabetes');
console.log(diabetesVars.map(v => v.nhanes_code));
// ["DIQ010", "LBXGLU", "LBXIN", "LBXGH", ...]

// Get variable suggestions for a research question
const suggestions = nhanesDict.suggestVariables('Does CRP predict cardiovascular events?');
console.log(suggestions.primary.map(v => v.nhanes_code));
// ["LBXCRP", "RIDAGEYR", "RIAGENDR", "BMXBMI", ...]
```

## Variable Information

```typescript
// Get detailed variable information
const variable = nhanesDict.lookupVariable('crp');
console.log(variable);
/*
{
  nhanes_code: "LBXCRP",
  label: "C-reactive protein (mg/dL)",
  description: "C-reactive protein level in blood",
  data_type: "continuous",
  unit: "mg/dL",
  range: [0, 50],
  component: "Laboratory",
  cycles: ["2015-2016", "2017-2018", "2019-2020"],
  aliases: ["c_reactive_protein", "c-reactive_protein"],
  clinical_significance: "Marker of inflammation, cardiovascular risk"
}
*/
```

## Data File Information

```typescript
// Get data file information
const labFiles = nhanesDict.getDataFileInfo('Laboratory');
console.log(labFiles);
/*
{
  file_prefix: "LAB",
  cycles: {
    "2015-2016": "LAB25_I",
    "2017-2018": "LAB25_J",
    "2019-2020": "LAB25_K"
  }
}
*/

// Get specific file name
const fileName = nhanesDict.getFileName('Laboratory', '2019-2020');
console.log(fileName); // "LAB25_K"
```

## Categories and Organization

```typescript
// Get all categories
const categories = nhanesDict.getCategories();
console.log(categories);
// ["demographics", "anthropometry", "laboratory", "blood_pressure", "lifestyle", "medical_conditions"]

// Get variables in a category
const labVars = nhanesDict.getCategoryVariables('laboratory');
console.log(Object.keys(labVars));
// ["crp", "glucose", "insulin", "hba1c", "total_cholesterol", ...]

// Get variables available in specific cycles
const vars2019 = nhanesDict.getVariablesByCycle('2019-2020');
console.log(vars2019.length); // Number of variables in 2019-2020 cycle
```

## Available Research Areas

### Cardiovascular Risk
Variables commonly used in cardiovascular risk research:
- Demographics: age, sex, race_ethnicity
- Anthropometry: bmi
- Blood pressure: systolic_bp, diastolic_bp
- Laboratory: total_cholesterol, hdl_cholesterol, ldl_cholesterol
- Lifestyle: smoking
- Medical conditions: diabetes, hypertension

### Metabolic Syndrome
Variables for metabolic syndrome assessment:
- waist_circumference, triglycerides, hdl_cholesterol
- systolic_bp, diastolic_bp, glucose

### Inflammation
Inflammatory markers and related variables:
- crp, age, sex, bmi, smoking, physical_activity

### Diabetes Research
Variables commonly used in diabetes research:
- glucose, insulin, hba1c, bmi, age, race_ethnicity
- diabetes, physical_activity

## Variable Categories

### Demographics
- **sequence_number** → SEQN (required for merging)
- **sex** → RIAGENDR
- **age** → RIDAGEYR
- **race_ethnicity** → RIDRETH3

### Anthropometry
- **bmi** → BMXBMI
- **weight** → BMXWT
- **height** → BMXHT
- **waist_circumference** → BMXWAIST

### Laboratory
- **crp** → LBXCRP (C-reactive protein)
- **glucose** → LBXGLU (Fasting glucose)
- **insulin** → LBXIN (Fasting insulin)
- **hba1c** → LBXGH (Hemoglobin A1c)
- **total_cholesterol** → LBXTC
- **hdl_cholesterol** → LBDHDD
- **ldl_cholesterol** → LBDLDL
- **triglycerides** → LBXTR

### Blood Pressure
- **systolic_bp** → BPXSY1
- **diastolic_bp** → BPXDI1

### Lifestyle
- **smoking** → SMQ020
- **alcohol_use** → ALQ101
- **physical_activity** → PAQ605

### Medical Conditions
- **diabetes** → DIQ010
- **hypertension** → BPQ020
- **heart_disease** → MCQ160C
- **stroke** → MCQ160F

## Data Types and Validation

The dictionary includes data type information for each variable:

- **continuous**: Numeric values (e.g., BMI, age)
- **categorical**: Discrete categories (e.g., sex, race)
- **integer**: Whole numbers (e.g., sequence numbers)

Each variable includes:
- Valid ranges for continuous variables
- Category mappings for categorical variables
- Units of measurement
- Clinical significance

## NHANES Cycles Covered

- 2015-2016 (cycle I)
- 2017-2018 (cycle J)
- 2019-2020 (cycle K)

## Advanced Usage

```typescript
import { NhanesVariableDictionary, nhanesData } from '@synthai/nhanes-dict';

// Create custom instance
const customDict = new NhanesVariableDictionary();

// Access raw data
console.log(nhanesData.metadata.version);

// Validate variable data
try {
  const validatedVar = customDict.validateVariable(someVariableData);
  console.log('Variable is valid:', validatedVar);
} catch (error) {
  console.log('Validation failed:', error);
}
```

## Contributing

To add new variables or research areas:

1. Edit `nhanes-variables.json`
2. Add the variable to the appropriate category
3. Update research mappings if needed
4. Run validation: `npm run validate`

## License

MIT License - see LICENSE file for details.