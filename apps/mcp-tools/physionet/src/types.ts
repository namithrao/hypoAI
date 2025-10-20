import { z } from 'zod';

export const PhysioNetCatalogSchema = z.object({
  query: z.string().optional(),
  category: z.enum([
    'ecg',
    'eeg',
    'emg',
    'clinical',
    'waveform',
    'annotation',
    'all'
  ]).optional().default('all'),
  limit: z.number().optional().default(50),
  offset: z.number().optional().default(0),
  dry_run: z.boolean().optional().default(false),
});

export const PhysioNetFetchSchema = z.object({
  dataset: z.string(),
  files: z.array(z.string()).optional(),
  columns: z.array(z.string()).optional(),
  limit: z.number().optional().default(10000),
  offset: z.number().optional().default(0),
  dry_run: z.boolean().optional().default(false),
});

export type PhysioNetCatalogQuery = z.infer<typeof PhysioNetCatalogSchema>;
export type PhysioNetFetchQuery = z.infer<typeof PhysioNetFetchSchema>;

export interface PhysioNetProvenance {
  source: 'PhysioNet';
  dataset: string;
  version: string;
  date: string;
  license: string;
  request_params: PhysioNetCatalogQuery | PhysioNetFetchQuery;
  request_timestamp: string;
  sha256_hash?: string;
}

export interface PhysioNetCatalogResult {
  datasets?: PhysioNetDataset[];
  estimated_count?: number;
  actual_count?: number;
  provenance: PhysioNetProvenance;
  errors?: string[];
  warnings?: string[];
}

export interface PhysioNetFetchResult {
  data?: Record<string, unknown>[];
  estimated_rows?: number;
  actual_rows?: number;
  provenance: PhysioNetProvenance;
  columns: string[];
  errors?: string[];
  warnings?: string[];
}

export interface PhysioNetDataset {
  id: string;
  title: string;
  description: string;
  category: string;
  authors: string[];
  publication_date: string;
  version: string;
  license: string;
  doi?: string;
  size_bytes: number;
  file_count: number;
  subject_count?: number;
  sampling_frequency?: number;
  duration?: string;
  files: PhysioNetFile[];
  tags: string[];
  allowlisted: boolean;
}

export interface PhysioNetFile {
  name: string;
  path: string;
  size_bytes: number;
  format: string;
  description: string;
  columns?: PhysioNetColumn[];
  sample_count?: number;
  duration?: number;
}

export interface PhysioNetColumn {
  name: string;
  description: string;
  unit: string;
  data_type: string;
  sampling_frequency?: number;
  gain?: number;
  baseline?: number;
}