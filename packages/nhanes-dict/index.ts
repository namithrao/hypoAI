import { z } from 'zod';
import nhanesData from './nhanes-variables.json';

// Type definitions
export interface NhanesVariable {
  nhanes_code: string;
  label: string;
  description: string;
  data_type: 'continuous' | 'categorical' | 'integer';
  unit?: string;
  range?: [number, number];
  values?: Record<string, string>;
  component: string;
  cycles: string[];
  aliases?: string[];
  required_for_merge?: boolean;
  clinical_significance?: string;
}

export interface NhanesCategory {
  description: string;
  variables: Record<string, NhanesVariable>;
}

export interface NhanesDataFile {
  file_prefix: string;
  cycles: Record<string, string>;
  description?: string;
}

export interface NhanesDictionary {
  metadata: {
    version: string;
    last_updated: string;
    description: string;
    source: string;
    cycles_covered: string[];
  };
  categories: Record<string, NhanesCategory>;
  common_research_mappings: Record<string, {
    description: string;
    variables: string[];
  }>;
  data_files_by_component: Record<string, NhanesDataFile>;
}

// Validation schema
export const NhanesVariableSchema = z.object({
  nhanes_code: z.string(),
  label: z.string(),
  description: z.string(),
  data_type: z.enum(['continuous', 'categorical', 'integer']),
  unit: z.string().optional(),
  range: z.tuple([z.number(), z.number()]).optional(),
  values: z.record(z.string()).optional(),
  component: z.string(),
  cycles: z.array(z.string()),
  aliases: z.array(z.string()).optional(),
  required_for_merge: z.boolean().optional(),
  clinical_significance: z.string().optional(),
});

// Main dictionary class
export class NhanesVariableDictionary {
  private data: NhanesDictionary;

  constructor() {
    this.data = nhanesData as NhanesDictionary;
  }

  /**
   * Get all variable categories
   */
  getCategories(): string[] {
    return Object.keys(this.data.categories);
  }

  /**
   * Get variables in a specific category
   */
  getCategoryVariables(category: string): Record<string, NhanesVariable> {
    const cat = this.data.categories[category];
    if (!cat) {
      throw new Error(`Category '${category}' not found`);
    }
    return cat.variables;
  }

  /**
   * Look up a variable by common name or alias
   */
  lookupVariable(searchTerm: string): NhanesVariable | null {
    const normalizedSearch = searchTerm.toLowerCase().replace(/[_-\s]/g, '');

    // Search through all categories
    for (const category of Object.values(this.data.categories)) {
      for (const [varName, variable] of Object.entries(category.variables)) {
        // Check direct name match
        if (varName.toLowerCase().replace(/[_-\s]/g, '') === normalizedSearch) {
          return variable;
        }

        // Check NHANES code match
        if (variable.nhanes_code.toLowerCase() === searchTerm.toLowerCase()) {
          return variable;
        }

        // Check aliases
        if (variable.aliases) {
          for (const alias of variable.aliases) {
            if (alias.toLowerCase().replace(/[_-\s]/g, '') === normalizedSearch) {
              return variable;
            }
          }
        }
      }
    }

    return null;
  }

  /**
   * Get NHANES variable code for a common term
   */
  getVariableCode(searchTerm: string): string | null {
    const variable = this.lookupVariable(searchTerm);
    return variable ? variable.nhanes_code : null;
  }

  /**
   * Get multiple variable codes at once
   */
  getVariableCodes(searchTerms: string[]): Record<string, string | null> {
    const result: Record<string, string | null> = {};
    for (const term of searchTerms) {
      result[term] = this.getVariableCode(term);
    }
    return result;
  }

  /**
   * Get variables for a common research area
   */
  getResearchVariables(researchArea: string): string[] {
    const mapping = this.data.common_research_mappings[researchArea];
    if (!mapping) {
      throw new Error(`Research area '${researchArea}' not found`);
    }
    return mapping.variables;
  }

  /**
   * Get NHANES codes for a research area
   */
  getResearchVariableCodes(researchArea: string): Record<string, string | null> {
    const variables = this.getResearchVariables(researchArea);
    return this.getVariableCodes(variables);
  }

  /**
   * Get all available research areas
   */
  getResearchAreas(): string[] {
    return Object.keys(this.data.common_research_mappings);
  }

  /**
   * Search variables by text
   */
  searchVariables(query: string): NhanesVariable[] {
    const results: NhanesVariable[] = [];
    const normalizedQuery = query.toLowerCase();

    for (const category of Object.values(this.data.categories)) {
      for (const variable of Object.values(category.variables)) {
        if (
          variable.label.toLowerCase().includes(normalizedQuery) ||
          variable.description.toLowerCase().includes(normalizedQuery) ||
          variable.nhanes_code.toLowerCase().includes(normalizedQuery) ||
          (variable.clinical_significance &&
           variable.clinical_significance.toLowerCase().includes(normalizedQuery))
        ) {
          results.push(variable);
        }
      }
    }

    return results;
  }

  /**
   * Get data file information for a component
   */
  getDataFileInfo(component: string): NhanesDataFile | null {
    return this.data.data_files_by_component[component] || null;
  }

  /**
   * Get file name for a component and cycle
   */
  getFileName(component: string, cycle: string): string | null {
    const fileInfo = this.getDataFileInfo(component);
    if (!fileInfo || !fileInfo.cycles[cycle]) {
      return null;
    }
    return fileInfo.cycles[cycle];
  }

  /**
   * Validate variable data against schema
   */
  validateVariable(variable: unknown): NhanesVariable {
    return NhanesVariableSchema.parse(variable);
  }

  /**
   * Get metadata about the dictionary
   */
  getMetadata() {
    return this.data.metadata;
  }

  /**
   * Get variables that are available in specific cycles
   */
  getVariablesByCycle(cycle: string): NhanesVariable[] {
    const results: NhanesVariable[] = [];

    for (const category of Object.values(this.data.categories)) {
      for (const variable of Object.values(category.variables)) {
        if (variable.cycles.includes(cycle)) {
          results.push(variable);
        }
      }
    }

    return results;
  }

  /**
   * Get suggested variables based on a research question
   */
  suggestVariables(question: string): {
    primary: NhanesVariable[];
    secondary: NhanesVariable[];
    research_area?: string;
  } {
    const normalizedQuestion = question.toLowerCase();

    // Try to match to research areas first
    for (const [area, mapping] of Object.entries(this.data.common_research_mappings)) {
      if (normalizedQuestion.includes(area.replace('_', ' ')) ||
          mapping.description.toLowerCase().split(' ').some(word =>
            normalizedQuestion.includes(word) && word.length > 3)) {

        const variables = mapping.variables.map(v => this.lookupVariable(v)).filter(Boolean) as NhanesVariable[];
        return {
          primary: variables.slice(0, 5),
          secondary: variables.slice(5),
          research_area: area
        };
      }
    }

    // Fall back to text search
    const searchResults = this.searchVariables(question);
    return {
      primary: searchResults.slice(0, 5),
      secondary: searchResults.slice(5, 10)
    };
  }
}

// Create and export a singleton instance
export const nhanesDict = new NhanesVariableDictionary();

// Export the raw data as well
export { nhanesData };

// Default export
export default NhanesVariableDictionary;