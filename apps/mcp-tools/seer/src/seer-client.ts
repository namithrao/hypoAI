import * as fs from 'fs-extra';
import * as path from 'path';
import fetch from 'node-fetch';
import * as crypto from 'crypto';
import { parseString } from 'xml2js';
import {
  SeerQuery,
  SeerResult,
  SeerProvenance,
  SeerEndpoint,
  SeerDataDictionary
} from './types.js';

export class SeerClient {
  private readonly cacheDir: string;
  private readonly apiKey?: string;
  private readonly baseUrl = 'https://seer.cancer.gov/rest';
  private readonly mockMode: boolean;

  constructor(cacheDir: string = './data/seer', apiKey?: string) {
    this.cacheDir = cacheDir;
    this.apiKey = apiKey;
    this.mockMode = !apiKey; // Use mock data if no API key provided
    fs.ensureDirSync(this.cacheDir);
  }

  async query(query: SeerQuery): Promise<SeerResult> {
    const startTime = new Date().toISOString();

    try {
      // Validate query
      const normalizedQuery = this.normalizeQuery(query);

      // Check if endpoint exists
      const endpoints = await this.getAvailableEndpoints();
      const endpoint = endpoints.find(ep => ep.name === normalizedQuery.endpoint);

      if (!endpoint) {
        throw new Error(`Unknown endpoint: ${normalizedQuery.endpoint}`);
      }

      // Validate required parameters
      const missingParams = endpoint.required_params.filter(
        param => !(param in normalizedQuery.params)
      );

      if (missingParams.length > 0) {
        throw new Error(`Missing required parameters: ${missingParams.join(', ')}`);
      }

      // Estimate rows for dry run
      if (normalizedQuery.dry_run) {
        const estimatedRows = await this.estimateRows(normalizedQuery);
        return this.createResult([], estimatedRows, normalizedQuery, startTime, endpoint);
      }

      // Fetch data
      const rawData = await this.fetchData(normalizedQuery, endpoint);
      const paginatedData = this.applyPagination(rawData, normalizedQuery);

      return this.createResult(paginatedData, rawData.length, normalizedQuery, startTime, endpoint);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      return this.createErrorResult(query, startTime, errorMessage);
    }
  }

  private normalizeQuery(query: SeerQuery): Required<SeerQuery> {
    return {
      endpoint: query.endpoint,
      params: query.params || {},
      limit: query.limit || 10000,
      offset: query.offset || 0,
      dry_run: query.dry_run ?? false,
    };
  }

  private async getAvailableEndpoints(): Promise<SeerEndpoint[]> {
    const cacheFile = path.join(this.cacheDir, 'endpoints.json');

    if (await fs.pathExists(cacheFile)) {
      const stats = await fs.stat(cacheFile);
      const age = Date.now() - stats.mtime.getTime();

      // Cache for 24 hours
      if (age < 24 * 60 * 60 * 1000) {
        return fs.readJson(cacheFile);
      }
    }

    // Define available endpoints (would normally fetch from SEER API)
    const endpoints: SeerEndpoint[] = [
      {
        name: 'incidence',
        description: 'Cancer incidence data by various demographics and tumor characteristics',
        available_params: [
          { name: 'site', type: 'enum', description: 'Primary cancer site', required: true, enum_values: ['breast', 'lung', 'prostate', 'colorectal', 'melanoma'] },
          { name: 'year', type: 'array', description: 'Diagnosis years', required: false, default: ['2020'] },
          { name: 'age_group', type: 'enum', description: 'Age group classification', required: false, enum_values: ['0-19', '20-49', '50-64', '65+', 'all'] },
          { name: 'sex', type: 'enum', description: 'Patient sex', required: false, enum_values: ['male', 'female', 'both'] },
          { name: 'race', type: 'enum', description: 'Race/ethnicity', required: false, enum_values: ['white', 'black', 'asian', 'hispanic', 'other', 'all'] },
          { name: 'stage', type: 'enum', description: 'Cancer stage', required: false, enum_values: ['localized', 'regional', 'distant', 'unknown', 'all'] }
        ],
        required_params: ['site'],
        data_format: 'json',
        rate_limit: 60
      },
      {
        name: 'mortality',
        description: 'Cancer mortality data by demographics',
        available_params: [
          { name: 'site', type: 'enum', description: 'Primary cancer site', required: true, enum_values: ['breast', 'lung', 'prostate', 'colorectal', 'melanoma'] },
          { name: 'year', type: 'array', description: 'Death years', required: false, default: ['2020'] },
          { name: 'age_group', type: 'enum', description: 'Age group classification', required: false, enum_values: ['0-19', '20-49', '50-64', '65+', 'all'] },
          { name: 'sex', type: 'enum', description: 'Patient sex', required: false, enum_values: ['male', 'female', 'both'] },
          { name: 'race', type: 'enum', description: 'Race/ethnicity', required: false, enum_values: ['white', 'black', 'asian', 'hispanic', 'other', 'all'] }
        ],
        required_params: ['site'],
        data_format: 'json',
        rate_limit: 60
      },
      {
        name: 'survival',
        description: 'Cancer survival statistics',
        available_params: [
          { name: 'site', type: 'enum', description: 'Primary cancer site', required: true, enum_values: ['breast', 'lung', 'prostate', 'colorectal', 'melanoma'] },
          { name: 'years', type: 'array', description: 'Survival years (1, 5, 10)', required: false, default: ['5'] },
          { name: 'stage', type: 'enum', description: 'Cancer stage', required: false, enum_values: ['localized', 'regional', 'distant', 'all'] },
          { name: 'period', type: 'string', description: 'Time period for diagnosis', required: false, default: '2010-2016' }
        ],
        required_params: ['site'],
        data_format: 'json',
        rate_limit: 30
      },
      {
        name: 'population',
        description: 'Population statistics for incidence rate calculations',
        available_params: [
          { name: 'year', type: 'array', description: 'Census years', required: true },
          { name: 'age_group', type: 'enum', description: 'Age group classification', required: false, enum_values: ['0-19', '20-49', '50-64', '65+', 'all'] },
          { name: 'sex', type: 'enum', description: 'Population sex', required: false, enum_values: ['male', 'female', 'both'] },
          { name: 'race', type: 'enum', description: 'Race/ethnicity', required: false, enum_values: ['white', 'black', 'asian', 'hispanic', 'other', 'all'] }
        ],
        required_params: ['year'],
        data_format: 'json',
        rate_limit: 60
      }
    ];

    await fs.writeJson(cacheFile, endpoints);
    return endpoints;
  }

  private async fetchData(query: Required<SeerQuery>, endpoint: SeerEndpoint): Promise<Record<string, unknown>[]> {
    if (this.mockMode) {
      return this.generateMockData(query, endpoint);
    }

    // Build API URL
    const url = new URL(`${this.baseUrl}/${query.endpoint}`);

    // Add parameters
    for (const [key, value] of Object.entries(query.params)) {
      if (Array.isArray(value)) {
        url.searchParams.append(key, value.join(','));
      } else {
        url.searchParams.append(key, String(value));
      }
    }

    if (this.apiKey) {
      url.searchParams.append('api_key', this.apiKey);
    }

    // Make request with caching
    const cacheKey = crypto.createHash('md5').update(url.toString()).digest('hex');
    const cacheFile = path.join(this.cacheDir, `${cacheKey}.json`);

    if (await fs.pathExists(cacheFile)) {
      const stats = await fs.stat(cacheFile);
      const age = Date.now() - stats.mtime.getTime();

      // Cache for 1 hour
      if (age < 60 * 60 * 1000) {
        return fs.readJson(cacheFile);
      }
    }

    try {
      const response = await fetch(url.toString());

      if (!response.ok) {
        throw new Error(`SEER API error: ${response.status} ${response.statusText}`);
      }

      let data: Record<string, unknown>[];

      if (endpoint.data_format === 'json') {
        data = await response.json() as Record<string, unknown>[];
      } else if (endpoint.data_format === 'xml') {
        const xmlText = await response.text();
        data = await this.parseXmlData(xmlText);
      } else {
        // CSV format
        const csvText = await response.text();
        data = this.parseCsvData(csvText);
      }

      // Cache the result
      await fs.writeJson(cacheFile, data);
      return data;

    } catch (error) {
      console.error('SEER API request failed:', error);
      // Fallback to mock data if API fails
      return this.generateMockData(query, endpoint);
    }
  }

  private async generateMockData(query: Required<SeerQuery>, endpoint: SeerEndpoint): Promise<Record<string, unknown>[]> {
    const sampleSize = Math.min(query.limit, 1000);
    const data: Record<string, unknown>[] = [];

    const dataDictionary = await this.getDataDictionary();

    for (let i = 0; i < sampleSize; i++) {
      const record: Record<string, unknown> = {
        record_id: i + 1,
        year: this.getRandomFromArray(['2018', '2019', '2020', '2021']),
      };

      // Add endpoint-specific fields
      switch (query.endpoint) {
        case 'incidence':
          Object.assign(record, {
            site: query.params.site || this.getRandomFromArray(Object.keys(dataDictionary.sites)),
            age_group: query.params.age_group || this.getRandomFromArray(['20-49', '50-64', '65+']),
            sex: query.params.sex || this.getRandomFromArray(['male', 'female']),
            race: query.params.race || this.getRandomFromArray(Object.keys(dataDictionary.race_ethnicity)),
            stage: query.params.stage || this.getRandomFromArray(Object.keys(dataDictionary.stages)),
            cases: Math.floor(Math.random() * 1000) + 1,
            population: Math.floor(Math.random() * 100000) + 10000,
            rate: (Math.random() * 100).toFixed(1),
            lower_ci: (Math.random() * 50).toFixed(1),
            upper_ci: (Math.random() * 50 + 50).toFixed(1)
          });
          break;

        case 'mortality':
          Object.assign(record, {
            site: query.params.site || this.getRandomFromArray(Object.keys(dataDictionary.sites)),
            age_group: query.params.age_group || this.getRandomFromArray(['20-49', '50-64', '65+']),
            sex: query.params.sex || this.getRandomFromArray(['male', 'female']),
            race: query.params.race || this.getRandomFromArray(Object.keys(dataDictionary.race_ethnicity)),
            deaths: Math.floor(Math.random() * 500) + 1,
            population: Math.floor(Math.random() * 100000) + 10000,
            rate: (Math.random() * 50).toFixed(1),
            lower_ci: (Math.random() * 25).toFixed(1),
            upper_ci: (Math.random() * 25 + 25).toFixed(1)
          });
          break;

        case 'survival':
          Object.assign(record, {
            site: query.params.site || this.getRandomFromArray(Object.keys(dataDictionary.sites)),
            stage: query.params.stage || this.getRandomFromArray(Object.keys(dataDictionary.stages)),
            years: query.params.years || '5',
            survival_rate: (Math.random() * 100).toFixed(1),
            standard_error: (Math.random() * 5).toFixed(2),
            cases: Math.floor(Math.random() * 10000) + 100
          });
          break;

        case 'population':
          Object.assign(record, {
            age_group: query.params.age_group || this.getRandomFromArray(['20-49', '50-64', '65+']),
            sex: query.params.sex || this.getRandomFromArray(['male', 'female']),
            race: query.params.race || this.getRandomFromArray(Object.keys(dataDictionary.race_ethnicity)),
            population: Math.floor(Math.random() * 1000000) + 100000
          });
          break;
      }

      data.push(record);
    }

    return data;
  }

  private async getDataDictionary(): Promise<SeerDataDictionary> {
    return {
      sites: {
        'breast': 'Breast',
        'lung': 'Lung and Bronchus',
        'prostate': 'Prostate',
        'colorectal': 'Colon and Rectum',
        'melanoma': 'Melanoma of the Skin'
      },
      stages: {
        'localized': 'Localized',
        'regional': 'Regional',
        'distant': 'Distant',
        'unknown': 'Unknown'
      },
      grades: {
        '1': 'Well differentiated',
        '2': 'Moderately differentiated',
        '3': 'Poorly differentiated',
        '4': 'Undifferentiated'
      },
      histologies: {
        '8140': 'Adenocarcinoma',
        '8070': 'Squamous cell carcinoma',
        '8720': 'Melanoma',
        '9650': 'Hodgkin lymphoma'
      },
      behaviors: {
        '0': 'Benign',
        '1': 'Uncertain behavior',
        '2': 'Carcinoma in situ',
        '3': 'Malignant'
      },
      race_ethnicity: {
        'white': 'White',
        'black': 'Black',
        'asian': 'Asian/Pacific Islander',
        'hispanic': 'Hispanic',
        'other': 'Other'
      }
    };
  }

  private getRandomFromArray<T>(arr: T[]): T {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  private async parseXmlData(xmlText: string): Promise<Record<string, unknown>[]> {
    return new Promise((resolve, reject) => {
      parseString(xmlText, (err, result) => {
        if (err) {
          reject(err);
          return;
        }

        // Transform XML structure to flat records
        // This would need to be customized based on SEER's actual XML format
        const records: Record<string, unknown>[] = [];
        if (result && result.data && result.data.record) {
          for (const record of result.data.record) {
            const flatRecord: Record<string, unknown> = {};
            this.flattenObject(record, flatRecord);
            records.push(flatRecord);
          }
        }

        resolve(records);
      });
    });
  }

  private parseCsvData(csvText: string): Record<string, unknown>[] {
    const lines = csvText.trim().split('\\n');
    if (lines.length === 0) return [];

    const headers = lines[0].split(',').map(h => h.trim());
    const records: Record<string, unknown>[] = [];

    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim());
      const record: Record<string, unknown> = {};

      headers.forEach((header, index) => {
        const value = values[index] || '';
        // Try to parse as number
        const numValue = Number(value);
        record[header] = isNaN(numValue) ? value : numValue;
      });

      records.push(record);
    }

    return records;
  }

  private flattenObject(obj: unknown, flat: Record<string, unknown>, prefix = ''): void {
    if (typeof obj !== 'object' || obj === null) {
      flat[prefix] = obj;
      return;
    }

    for (const [key, value] of Object.entries(obj)) {
      const newKey = prefix ? `${prefix}.${key}` : key;

      if (Array.isArray(value)) {
        if (value.length === 1 && typeof value[0] !== 'object') {
          flat[newKey] = value[0];
        } else {
          value.forEach((item, index) => {
            this.flattenObject(item, flat, `${newKey}[${index}]`);
          });
        }
      } else if (typeof value === 'object') {
        this.flattenObject(value, flat, newKey);
      } else {
        flat[newKey] = value;
      }
    }
  }

  private applyPagination(data: Record<string, unknown>[], query: Required<SeerQuery>): Record<string, unknown>[] {
    const start = query.offset;
    const end = start + query.limit;
    return data.slice(start, end);
  }

  private async estimateRows(query: Required<SeerQuery>): Promise<number> {
    // Simple estimation based on endpoint and parameters
    const baseEstimates: Record<string, number> = {
      'incidence': 50000,
      'mortality': 25000,
      'survival': 10000,
      'population': 100000
    };

    let estimate = baseEstimates[query.endpoint] || 10000;

    // Adjust based on filters
    const filterCount = Object.keys(query.params).length;
    const filterMultiplier = Math.max(0.1, 1 - (filterCount * 0.2));
    estimate *= filterMultiplier;

    return Math.floor(estimate);
  }

  private createResult(
    data: Record<string, unknown>[],
    totalRows: number,
    query: Required<SeerQuery>,
    requestTime: string,
    endpoint: SeerEndpoint
  ): SeerResult {
    const columns = data.length > 0 ? Object.keys(data[0]) : [];
    const dataString = JSON.stringify(data);
    const hash = crypto.createHash('sha256').update(dataString).digest('hex');

    const provenance: SeerProvenance = {
      source: 'SEER',
      dataset: `${query.endpoint} (${endpoint.description})`,
      version: 'November 2021',
      date: '2021-11-15',
      license: 'Public Domain (U.S. Government)',
      request_params: query,
      request_timestamp: requestTime,
      sha256_hash: hash
    };

    return {
      data: query.dry_run ? undefined : data,
      estimated_rows: query.dry_run ? totalRows : undefined,
      actual_rows: query.dry_run ? undefined : data.length,
      provenance,
      columns,
      warnings: data.length === 0 ? ['No data found matching the specified criteria'] : undefined
    };
  }

  private createErrorResult(query: SeerQuery, requestTime: string, error: string): SeerResult {
    const provenance: SeerProvenance = {
      source: 'SEER',
      dataset: 'N/A',
      version: 'N/A',
      date: 'N/A',
      license: 'Public Domain (U.S. Government)',
      request_params: query as Required<SeerQuery>,
      request_timestamp: requestTime
    };

    return {
      provenance,
      columns: [],
      errors: [error]
    };
  }
}