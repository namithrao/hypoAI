import { z } from 'zod';

export const SeerQuerySchema = z.object({
  endpoint: z.enum([
    'incidence',
    'mortality',
    'survival',
    'population',
    'sites',
    'demographics'
  ]),
  params: z.record(z.union([
    z.string(),
    z.number(),
    z.array(z.union([z.string(), z.number()]))
  ])).optional().default({}),
  limit: z.number().optional().default(10000),
  offset: z.number().optional().default(0),
  dry_run: z.boolean().optional().default(false),
});

export type SeerQuery = z.infer<typeof SeerQuerySchema>;

export interface SeerProvenance {
  source: 'SEER';
  dataset: string;
  version: string;
  date: string;
  license: string;
  request_params: SeerQuery;
  request_timestamp: string;
  sha256_hash?: string;
}

export interface SeerResult {
  data?: Record<string, unknown>[];
  estimated_rows?: number;
  actual_rows?: number;
  provenance: SeerProvenance;
  columns: string[];
  errors?: string[];
  warnings?: string[];
}

export interface SeerEndpoint {
  name: string;
  description: string;
  available_params: SeerParam[];
  required_params: string[];
  data_format: 'json' | 'xml' | 'csv';
  rate_limit: number; // requests per minute
}

export interface SeerParam {
  name: string;
  type: 'string' | 'number' | 'array' | 'enum';
  description: string;
  required: boolean;
  default?: unknown;
  enum_values?: string[];
  min?: number;
  max?: number;
}

export interface SeerDataDictionary {
  sites: Record<string, string>;
  stages: Record<string, string>;
  grades: Record<string, string>;
  histologies: Record<string, string>;
  behaviors: Record<string, string>;
  race_ethnicity: Record<string, string>;
}