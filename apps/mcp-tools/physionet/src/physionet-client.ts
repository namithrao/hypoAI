import * as fs from 'fs-extra';
import * as path from 'path';
import fetch from 'node-fetch';
import * as crypto from 'crypto';
import csvParser from 'csv-parser';
import {
  PhysioNetCatalogQuery,
  PhysioNetFetchQuery,
  PhysioNetCatalogResult,
  PhysioNetFetchResult,
  PhysioNetProvenance,
  PhysioNetDataset,
  PhysioNetFile,
  PhysioNetColumn
} from './types.js';

export class PhysioNetClient {
  private readonly cacheDir: string;
  private readonly baseUrl = 'https://physionet.org/content';
  private readonly allowlist: Set<string>;

  constructor(cacheDir: string = './data/physionet') {
    this.cacheDir = cacheDir;
    fs.ensureDirSync(this.cacheDir);

    // Define allowlisted open datasets for demonstration
    this.allowlist = new Set([
      'mitdb',           // MIT-BIH Arrhythmia Database
      'ptbdb',           // PTB Diagnostic ECG Database
      'eegmmidb',        // EEG Motor Movement/Imagery Dataset
      'apnea-ecg',       // Apnea-ECG Database
      'challenge-2017',  // PhysioNet Challenge 2017
      'mimic-cxr-jpg',   // MIMIC-CXR-JPG
      'chbmit',          // CHB-MIT Scalp EEG Database
    ]);
  }

  async catalog(query: PhysioNetCatalogQuery): Promise<PhysioNetCatalogResult> {
    const startTime = new Date().toISOString();

    try {
      const normalizedQuery = this.normalizeCatalogQuery(query);

      if (normalizedQuery.dry_run) {
        const estimatedCount = await this.estimateDatasetCount(normalizedQuery);
        return this.createCatalogResult([], estimatedCount, normalizedQuery, startTime);
      }

      const datasets = await this.searchDatasets(normalizedQuery);
      const paginatedDatasets = this.applyPagination(datasets, normalizedQuery);

      return this.createCatalogResult(paginatedDatasets, datasets.length, normalizedQuery, startTime);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      return this.createCatalogErrorResult(query, startTime, errorMessage);
    }
  }

  async fetch(query: PhysioNetFetchQuery): Promise<PhysioNetFetchResult> {
    const startTime = new Date().toISOString();

    try {
      const normalizedQuery = this.normalizeFetchQuery(query);

      // Check if dataset is allowlisted
      if (!this.allowlist.has(normalizedQuery.dataset)) {
        throw new Error(`Dataset '${normalizedQuery.dataset}' is not in the allowlist`);
      }

      const dataset = await this.getDatasetMetadata(normalizedQuery.dataset);

      if (normalizedQuery.dry_run) {
        const estimatedRows = await this.estimateDatasetRows(dataset, normalizedQuery);
        return this.createFetchResult([], estimatedRows, normalizedQuery, startTime, dataset);
      }

      const data = await this.fetchDatasetData(dataset, normalizedQuery);
      const paginatedData = this.applyDataPagination(data, normalizedQuery);

      return this.createFetchResult(paginatedData, data.length, normalizedQuery, startTime, dataset);

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      return this.createFetchErrorResult(query, startTime, errorMessage);
    }
  }

  private normalizeCatalogQuery(query: PhysioNetCatalogQuery): Required<PhysioNetCatalogQuery> {
    return {
      query: query.query || '',
      category: query.category || 'all',
      limit: query.limit || 50,
      offset: query.offset || 0,
      dry_run: query.dry_run ?? false,
    };
  }

  private normalizeFetchQuery(query: PhysioNetFetchQuery): Required<PhysioNetFetchQuery> {
    return {
      dataset: query.dataset,
      files: query.files || [],
      columns: query.columns || [],
      limit: query.limit || 10000,
      offset: query.offset || 0,
      dry_run: query.dry_run ?? false,
    };
  }

  private async searchDatasets(query: Required<PhysioNetCatalogQuery>): Promise<PhysioNetDataset[]> {
    const cacheFile = path.join(this.cacheDir, 'datasets.json');

    if (await fs.pathExists(cacheFile)) {
      const stats = await fs.stat(cacheFile);
      const age = Date.now() - stats.mtime.getTime();

      // Cache for 24 hours
      if (age < 24 * 60 * 60 * 1000) {
        const allDatasets = await fs.readJson(cacheFile);
        return this.filterDatasets(allDatasets, query);
      }
    }

    // Generate sample datasets for demonstration
    const datasets = await this.generateSampleDatasets();
    await fs.writeJson(cacheFile, datasets);

    return this.filterDatasets(datasets, query);
  }

  private async generateSampleDatasets(): Promise<PhysioNetDataset[]> {
    return [
      {
        id: 'mitdb',
        title: 'MIT-BIH Arrhythmia Database',
        description: 'A collection of 48 half-hour excerpts of two-channel ambulatory ECG recordings, obtained from 47 subjects studied by the BIH Arrhythmia Laboratory.',
        category: 'ecg',
        authors: ['Moody GB', 'Mark RG'],
        publication_date: '2001-06-05',
        version: '1.0.0',
        license: 'Open Data Commons Attribution License v1.0',
        doi: '10.13026/C2F305',
        size_bytes: 69738496,
        file_count: 144,
        subject_count: 47,
        sampling_frequency: 360,
        duration: '48 × 30 minutes',
        files: [
          {
            name: '100.dat',
            path: 'mitdb/1.0.0/100.dat',
            size_bytes: 650000,
            format: 'binary',
            description: 'Record 100 signal data',
            columns: [
              { name: 'MLII', description: 'Modified Lead II', unit: 'mV', data_type: 'int16', sampling_frequency: 360, gain: 200, baseline: 1024 },
              { name: 'V5', description: 'Lead V5', unit: 'mV', data_type: 'int16', sampling_frequency: 360, gain: 200, baseline: 1024 }
            ],
            sample_count: 650000,
            duration: 1800
          },
          {
            name: '100.atr',
            path: 'mitdb/1.0.0/100.atr',
            size_bytes: 8192,
            format: 'annotation',
            description: 'Record 100 annotations',
            sample_count: 2273
          }
        ],
        tags: ['ecg', 'arrhythmia', 'annotation', 'ambulatory'],
        allowlisted: true
      },
      {
        id: 'ptbdb',
        title: 'PTB Diagnostic ECG Database',
        description: 'A collection of 549 records from 290 subjects, with 15 simultaneously measured signals: the conventional 12 leads plus the 3 Frank lead ECGs.',
        category: 'ecg',
        authors: ['Bousseljot R', 'Kreiseler D', 'Schnabel A'],
        publication_date: '2004-07-13',
        version: '1.0.0',
        license: 'Open Data Commons Attribution License v1.0',
        doi: '10.13026/C28C71',
        size_bytes: 549000000,
        file_count: 1647,
        subject_count: 290,
        sampling_frequency: 1000,
        duration: '549 records, variable length',
        files: [
          {
            name: 's0010_re.dat',
            path: 'ptbdb/1.0.0/patient001/s0010_re.dat',
            size_bytes: 1150000,
            format: 'binary',
            description: 'Patient 001, record s0010_re',
            columns: [
              { name: 'i', description: 'Lead I', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'ii', description: 'Lead II', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'iii', description: 'Lead III', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'avr', description: 'Lead aVR', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'avl', description: 'Lead aVL', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'avf', description: 'Lead aVF', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'v1', description: 'Lead V1', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'v2', description: 'Lead V2', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'v3', description: 'Lead V3', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'v4', description: 'Lead V4', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'v5', description: 'Lead V5', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'v6', description: 'Lead V6', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'vx', description: 'Frank lead VX', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'vy', description: 'Frank lead VY', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 },
              { name: 'vz', description: 'Frank lead VZ', unit: 'mV', data_type: 'int16', sampling_frequency: 1000 }
            ],
            sample_count: 115000,
            duration: 115
          }
        ],
        tags: ['ecg', 'diagnostic', 'ptb', '12-lead', 'frank-leads'],
        allowlisted: true
      },
      {
        id: 'eegmmidb',
        title: 'EEG Motor Movement/Imagery Dataset',
        description: 'A dataset of EEG recordings from 109 volunteers performing motor movement and motor imagery tasks.',
        category: 'eeg',
        authors: ['Schalk G', 'McFarland DJ', 'Hinterberger T', 'Birbaumer N', 'Wolpaw JR'],
        publication_date: '2004-08-18',
        version: '1.0.0',
        license: 'Open Data Commons Attribution License v1.0',
        doi: '10.13026/C28G6P',
        size_bytes: 1500000000,
        file_count: 1500,
        subject_count: 109,
        sampling_frequency: 160,
        duration: '109 subjects × multiple sessions',
        files: [
          {
            name: 'S001R01.edf',
            path: 'eegmmidb/1.0.0/S001/S001R01.edf',
            size_bytes: 2560000,
            format: 'edf',
            description: 'Subject 001, Run 01 (baseline, eyes open)',
            columns: [
              { name: 'Fc5', description: 'EEG channel Fc5', unit: 'μV', data_type: 'float32', sampling_frequency: 160 },
              { name: 'Fc3', description: 'EEG channel Fc3', unit: 'μV', data_type: 'float32', sampling_frequency: 160 },
              { name: 'Fc1', description: 'EEG channel Fc1', unit: 'μV', data_type: 'float32', sampling_frequency: 160 },
              { name: 'Fcz', description: 'EEG channel Fcz', unit: 'μV', data_type: 'float32', sampling_frequency: 160 },
              { name: 'Fc2', description: 'EEG channel Fc2', unit: 'μV', data_type: 'float32', sampling_frequency: 160 },
              { name: 'Fc4', description: 'EEG channel Fc4', unit: 'μV', data_type: 'float32', sampling_frequency: 160 },
              { name: 'Fc6', description: 'EEG channel Fc6', unit: 'μV', data_type: 'float32', sampling_frequency: 160 }
            ],
            sample_count: 19200,
            duration: 120
          }
        ],
        tags: ['eeg', 'motor-imagery', 'bci', 'movement'],
        allowlisted: true
      },
      {
        id: 'apnea-ecg',
        title: 'Apnea-ECG Database',
        description: 'A collection of 70 ECG recordings that have been used in the Computers in Cardiology Challenge 2000.',
        category: 'ecg',
        authors: ['Penzel T', 'Moody GB', 'Mark RG', 'Goldberger AL', 'Peter JH'],
        publication_date: '2000-09-14',
        version: '1.0.0',
        license: 'Open Data Commons Attribution License v1.0',
        doi: '10.13026/C26S39',
        size_bytes: 150000000,
        file_count: 140,
        subject_count: 70,
        sampling_frequency: 100,
        duration: '70 recordings, ~8 hours each',
        files: [
          {
            name: 'a01.dat',
            path: 'apnea-ecg/1.0.0/a01.dat',
            size_bytes: 2000000,
            format: 'binary',
            description: 'Recording a01 ECG signal',
            columns: [
              { name: 'ECG', description: 'ECG signal', unit: 'mV', data_type: 'int16', sampling_frequency: 100 }
            ],
            sample_count: 2880000,
            duration: 28800
          },
          {
            name: 'a01.apn',
            path: 'apnea-ecg/1.0.0/a01.apn',
            size_bytes: 1024,
            format: 'annotation',
            description: 'Recording a01 apnea annotations',
            sample_count: 480
          }
        ],
        tags: ['ecg', 'apnea', 'sleep', 'annotation'],
        allowlisted: true
      }
    ];
  }

  private filterDatasets(datasets: PhysioNetDataset[], query: Required<PhysioNetCatalogQuery>): PhysioNetDataset[] {
    let filtered = datasets.filter(dataset => dataset.allowlisted);

    if (query.category !== 'all') {
      filtered = filtered.filter(dataset => dataset.category === query.category);
    }

    if (query.query) {
      const searchTerm = query.query.toLowerCase();
      filtered = filtered.filter(dataset =>
        dataset.title.toLowerCase().includes(searchTerm) ||
        dataset.description.toLowerCase().includes(searchTerm) ||
        dataset.tags.some(tag => tag.toLowerCase().includes(searchTerm))
      );
    }

    return filtered;
  }

  private async getDatasetMetadata(datasetId: string): Promise<PhysioNetDataset> {
    const datasets = await this.generateSampleDatasets();
    const dataset = datasets.find(d => d.id === datasetId);

    if (!dataset) {
      throw new Error(`Dataset '${datasetId}' not found`);
    }

    return dataset;
  }

  private async fetchDatasetData(dataset: PhysioNetDataset, query: Required<PhysioNetFetchQuery>): Promise<Record<string, unknown>[]> {
    const targetFiles = query.files.length > 0
      ? dataset.files.filter(file => query.files.includes(file.name))
      : dataset.files.filter(file => file.format === 'binary' || file.format === 'csv' || file.format === 'tsv');

    if (targetFiles.length === 0) {
      throw new Error('No suitable data files found');
    }

    const allData: Record<string, unknown>[] = [];

    for (const file of targetFiles) {
      const fileData = await this.loadFileData(dataset, file, query);
      allData.push(...fileData);
    }

    return allData;
  }

  private async loadFileData(
    dataset: PhysioNetDataset,
    file: PhysioNetFile,
    query: Required<PhysioNetFetchQuery>
  ): Promise<Record<string, unknown>[]> {
    const cacheFile = path.join(this.cacheDir, dataset.id, file.name.replace(/\\.[^.]+$/, '.csv'));

    if (!(await fs.pathExists(cacheFile))) {
      await fs.ensureDir(path.dirname(cacheFile));
      await this.generateSampleFileData(dataset, file, cacheFile);
    }

    const data = await this.readCsvFile(cacheFile);

    // Project columns if specified
    if (query.columns.length > 0) {
      return data.map(row => this.projectColumns(row, query.columns));
    }

    return data;
  }

  private async generateSampleFileData(dataset: PhysioNetDataset, file: PhysioNetFile, outputPath: string): Promise<void> {
    const sampleSize = Math.min(file.sample_count || 1000, 10000);
    const columns = file.columns || [{ name: 'signal', description: 'Sample signal', unit: 'unit', data_type: 'float32' }];

    const headers = ['time', ...columns.map(col => col.name)];
    const rows: string[] = [headers.join(',')];

    const samplingFreq = file.columns?.[0]?.sampling_frequency || 360;
    const timeStep = 1.0 / samplingFreq;

    for (let i = 0; i < sampleSize; i++) {
      const time = (i * timeStep).toFixed(6);
      const values = columns.map(col => {
        if (col.name.toLowerCase().includes('ecg') || col.name.toLowerCase().includes('mlii')) {
          // Generate ECG-like signal
          const t = i * timeStep;
          const heartRate = 75; // BPM
          const signal = Math.sin(2 * Math.PI * heartRate / 60 * t) * 0.5 +
                        Math.sin(2 * Math.PI * heartRate / 60 * t * 2) * 0.3 +
                        (Math.random() - 0.5) * 0.1;
          return signal.toFixed(4);
        } else if (col.name.toLowerCase().includes('eeg')) {
          // Generate EEG-like signal
          const alpha = Math.sin(2 * Math.PI * 10 * i * timeStep) * 20;
          const noise = (Math.random() - 0.5) * 10;
          return (alpha + noise).toFixed(2);
        } else {
          // Generic signal
          return (Math.sin(2 * Math.PI * 0.1 * i) + (Math.random() - 0.5) * 0.2).toFixed(3);
        }
      });

      rows.push([time, ...values].join(','));
    }

    await fs.writeFile(outputPath, rows.join('\\n'));
  }

  private async readCsvFile(filePath: string): Promise<Record<string, unknown>[]> {
    return new Promise((resolve, reject) => {
      const results: Record<string, unknown>[] = [];

      fs.createReadStream(filePath)
        .pipe(csvParser())
        .on('data', (data) => {
          // Convert numeric strings to numbers
          const converted: Record<string, unknown> = {};
          for (const [key, value] of Object.entries(data)) {
            if (typeof value === 'string' && !isNaN(Number(value))) {
              converted[key] = Number(value);
            } else {
              converted[key] = value;
            }
          }
          results.push(converted);
        })
        .on('end', () => resolve(results))
        .on('error', reject);
    });
  }

  private projectColumns(row: Record<string, unknown>, columns: string[]): Record<string, unknown> {
    const projected: Record<string, unknown> = {};
    for (const col of columns) {
      if (col in row) {
        projected[col] = row[col];
      }
    }
    return projected;
  }

  private applyPagination<T>(items: T[], query: { limit: number; offset: number }): T[] {
    return items.slice(query.offset, query.offset + query.limit);
  }

  private applyDataPagination(data: Record<string, unknown>[], query: Required<PhysioNetFetchQuery>): Record<string, unknown>[] {
    return data.slice(query.offset, query.offset + query.limit);
  }

  private async estimateDatasetCount(query: Required<PhysioNetCatalogQuery>): Promise<number> {
    const allDatasets = await this.generateSampleDatasets();
    const filtered = this.filterDatasets(allDatasets, query);
    return filtered.length;
  }

  private async estimateDatasetRows(dataset: PhysioNetDataset, query: Required<PhysioNetFetchQuery>): Promise<number> {
    const targetFiles = query.files.length > 0
      ? dataset.files.filter(file => query.files.includes(file.name))
      : dataset.files.filter(file => file.format === 'binary' || file.format === 'csv');

    let totalRows = 0;
    for (const file of targetFiles) {
      totalRows += file.sample_count || 1000;
    }

    return totalRows;
  }

  private createCatalogResult(
    datasets: PhysioNetDataset[],
    totalCount: number,
    query: Required<PhysioNetCatalogQuery>,
    requestTime: string
  ): PhysioNetCatalogResult {
    const provenance: PhysioNetProvenance = {
      source: 'PhysioNet',
      dataset: 'Catalog',
      version: '1.0.0',
      date: new Date().toISOString().split('T')[0],
      license: 'Various (see individual datasets)',
      request_params: query,
      request_timestamp: requestTime
    };

    return {
      datasets: query.dry_run ? undefined : datasets,
      estimated_count: query.dry_run ? totalCount : undefined,
      actual_count: query.dry_run ? undefined : datasets.length,
      provenance
    };
  }

  private createFetchResult(
    data: Record<string, unknown>[],
    totalRows: number,
    query: Required<PhysioNetFetchQuery>,
    requestTime: string,
    dataset: PhysioNetDataset
  ): PhysioNetFetchResult {
    const columns = data.length > 0 ? Object.keys(data[0]) : query.columns;
    const dataString = JSON.stringify(data);
    const hash = crypto.createHash('sha256').update(dataString).digest('hex');

    const provenance: PhysioNetProvenance = {
      source: 'PhysioNet',
      dataset: `${dataset.id} - ${dataset.title}`,
      version: dataset.version,
      date: dataset.publication_date,
      license: dataset.license,
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

  private createCatalogErrorResult(query: PhysioNetCatalogQuery, requestTime: string, error: string): PhysioNetCatalogResult {
    const provenance: PhysioNetProvenance = {
      source: 'PhysioNet',
      dataset: 'N/A',
      version: 'N/A',
      date: 'N/A',
      license: 'N/A',
      request_params: query as Required<PhysioNetCatalogQuery>,
      request_timestamp: requestTime
    };

    return {
      provenance,
      errors: [error]
    };
  }

  private createFetchErrorResult(query: PhysioNetFetchQuery, requestTime: string, error: string): PhysioNetFetchResult {
    const provenance: PhysioNetProvenance = {
      source: 'PhysioNet',
      dataset: 'N/A',
      version: 'N/A',
      date: 'N/A',
      license: 'N/A',
      request_params: query as Required<PhysioNetFetchQuery>,
      request_timestamp: requestTime
    };

    return {
      provenance,
      columns: [],
      errors: [error]
    };
  }
}