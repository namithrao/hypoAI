import { NhanesClient } from '../src/nhanes-client';
import { NhanesQuery } from '../src/types';
import * as fs from 'fs-extra';
import * as path from 'path';

describe('NhanesClient', () => {
  let client: NhanesClient;
  let tempDir: string;

  beforeEach(async () => {
    tempDir = path.join(__dirname, 'temp', Date.now().toString());
    await fs.ensureDir(tempDir);
    client = new NhanesClient(tempDir);
  });

  afterEach(async () => {
    await fs.remove(tempDir);
  });

  describe('get method', () => {
    it('should return estimated rows for dry run', async () => {
      const query: NhanesQuery = {
        cycles: ['2019-2020'],
        columns: ['SEQN', 'LBXCRP'],
        dry_run: true
      };

      const result = await client.get(query);

      expect(result.estimated_rows).toBeGreaterThan(0);
      expect(result.data).toBeUndefined();
      expect(result.provenance.source).toBe('NHANES');
      expect(result.provenance.request_params).toEqual(expect.objectContaining(query));
    });

    it('should return actual data when not dry run', async () => {
      const query: NhanesQuery = {
        cycles: ['2019-2020'],
        columns: ['SEQN', 'RIAGENDR', 'RIDAGEYR'],
        limit: 10
      };

      const result = await client.get(query);

      expect(result.data).toBeDefined();
      expect(result.data!.length).toBeLessThanOrEqual(10);
      expect(result.actual_rows).toBe(result.data!.length);
      expect(result.columns).toContain('SEQN');
    });

    it('should apply age filters correctly', async () => {
      const query: NhanesQuery = {
        cycles: ['2019-2020'],
        columns: ['SEQN', 'RIDAGEYR'],
        where: {
          RIDAGEYR: [40, 65]
        },
        limit: 100
      };

      const result = await client.get(query);

      expect(result.data).toBeDefined();
      result.data!.forEach(row => {
        const age = Number(row.RIDAGEYR);
        expect(age).toBeGreaterThanOrEqual(40);
        expect(age).toBeLessThanOrEqual(65);
      });
    });

    it('should apply gender filters correctly', async () => {
      const query: NhanesQuery = {
        cycles: ['2019-2020'],
        columns: ['SEQN', 'RIAGENDR'],
        where: {
          RIAGENDR: 1  // Male
        },
        limit: 50
      };

      const result = await client.get(query);

      expect(result.data).toBeDefined();
      result.data!.forEach(row => {
        expect(row.RIAGENDR).toBe('1');
      });
    });

    it('should handle pagination correctly', async () => {
      const baseQuery: NhanesQuery = {
        cycles: ['2019-2020'],
        columns: ['SEQN'],
        limit: 5
      };

      const firstPage = await client.get({ ...baseQuery, offset: 0 });
      const secondPage = await client.get({ ...baseQuery, offset: 5 });

      expect(firstPage.data).toBeDefined();
      expect(secondPage.data).toBeDefined();
      expect(firstPage.data!.length).toBe(5);
      expect(secondPage.data!.length).toBe(5);

      // Check that SEQNs don't overlap
      const firstPageSEQNs = firstPage.data!.map(row => row.SEQN);
      const secondPageSEQNs = secondPage.data!.map(row => row.SEQN);
      const intersection = firstPageSEQNs.filter(seqn => secondPageSEQNs.includes(seqn));
      expect(intersection.length).toBe(0);
    });

    it('should include proper provenance information', async () => {
      const query: NhanesQuery = {
        cycles: ['2019-2020'],
        columns: ['SEQN', 'LBXCRP'],
        limit: 1
      };

      const result = await client.get(query);

      expect(result.provenance).toEqual(
        expect.objectContaining({
          source: 'NHANES',
          license: 'Public Domain (U.S. Government)',
          request_params: expect.objectContaining(query),
          request_timestamp: expect.any(String),
          sha256_hash: expect.any(String)
        })
      );
    });

    it('should handle empty results gracefully', async () => {
      const query: NhanesQuery = {
        cycles: ['2019-2020'],
        where: {
          RIDAGEYR: 999  // Impossible age
        }
      };

      const result = await client.get(query);

      expect(result.data).toBeDefined();
      expect(result.data!.length).toBe(0);
      expect(result.warnings).toContain('No data found matching the specified criteria');
    });

    it('should handle invalid cycles', async () => {
      const query: NhanesQuery = {
        cycles: ['1999-2000'],  // Old cycle that might not be available
        columns: ['SEQN']
      };

      const result = await client.get(query);

      // Should either return empty data or handle gracefully
      expect(result).toBeDefined();
      expect(result.provenance.source).toBe('NHANES');
    });

    it('should validate column projection', async () => {
      const query: NhanesQuery = {
        cycles: ['2019-2020'],
        columns: ['SEQN', 'LBXCRP', 'RIAGENDR'],
        limit: 5
      };

      const result = await client.get(query);

      expect(result.data).toBeDefined();
      expect(result.columns).toEqual(expect.arrayContaining(['SEQN', 'LBXCRP', 'RIAGENDR']));

      result.data!.forEach(row => {
        expect(Object.keys(row)).toEqual(expect.arrayContaining(['SEQN', 'LBXCRP', 'RIAGENDR']));
      });
    });
  });
});