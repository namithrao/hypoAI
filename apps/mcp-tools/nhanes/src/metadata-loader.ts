import fetch from 'node-fetch';
import * as cheerio from 'cheerio';

interface FileMetadata {
  category: string;
  fileName: string;
  fileCode: string;
  description: string;
  cycles: string[];
}

interface VariableMetadata {
  variableName: string;
  description: string;
  fileName: string;
  category: string;
  unit: string | null;
  cycles: string[];
}

class NHANESMetadataLoader {
  private fileMetadata: Map<string, FileMetadata> = new Map();
  private variableMetadata: Map<string, VariableMetadata[]> = new Map();

  async loadAllMetadata(): Promise<void> {
    console.error('Loading NHANES metadata from website...');

    const cycles = ['2017-2018', '2015-2016', '2013-2014', '2011-2012', '2009-2010'];
    const categories = ['demographics', 'dietary', 'examination', 'laboratory', 'questionnaire'];

    for (const category of categories) {
      for (const cycle of cycles) {
        await this.loadVariablesForCycle(category, cycle);
      }
    }

    console.error(`Loaded ${this.fileMetadata.size} unique files with ${this.getTotalVariableCount()} variables`);
  }

  private async loadVariablesForCycle(category: string, cycle: string): Promise<void> {
    const [beginYear, endYear] = cycle.split('-');
    const url = `https://wwwn.cdc.gov/nchs/nhanes/search/variablelist.aspx?Component=${this.capitalizeFirst(category)}&BeginYear=${beginYear}&EndYear=${endYear}`;

    try {
      const response = await fetch(url);
      const html = await response.text();
      const $ = cheerio.load(html);

      // Parse variable table
      const table = $('#GridView1');
      if (!table.length) return;

      table.find('tr').slice(1).each((_, row) => {
        const cells = $(row).find('td');
        if (cells.length < 7) return;

        const variableName = $(cells[0]).text().trim();
        const variableDesc = $(cells[1]).text().trim();
        const dataFileName = $(cells[2]).text().trim();
        const dataFileDesc = $(cells[3]).text().trim();
        const fileCategory = $(cells[6]).text().trim();

        // Store file metadata
        const fileKey = `${category}:${dataFileDesc}`;
        if (!this.fileMetadata.has(fileKey)) {
          this.fileMetadata.set(fileKey, {
            category: category,
            fileName: dataFileDesc,
            fileCode: dataFileName,
            description: dataFileDesc,
            cycles: [cycle]
          });
        } else {
          const existing = this.fileMetadata.get(fileKey)!;
          if (!existing.cycles.includes(cycle)) {
            existing.cycles.push(cycle);
          }
        }

        // Store variable metadata
        if (!this.variableMetadata.has(fileKey)) {
          this.variableMetadata.set(fileKey, []);
        }

        this.variableMetadata.get(fileKey)!.push({
          variableName,
          description: variableDesc,
          fileName: dataFileDesc,
          category: category,
          unit: this.extractUnit(variableDesc),
          cycles: [cycle]
        });
      });
    } catch (error: any) {
      console.error(`Failed to load ${category}/${cycle}: ${error.message}`);
    }
  }

  private extractUnit(description: string): string | null {
    // Extract unit from parentheses like "(mg/L)" or "(kg/m2)"
    const match = description.match(/\(([^)]*(?:mg|g|dL|L|mmol|umol|%|years?|cm|kg|m2)[^)]*)\)\s*$/i);
    return match ? match[1] : null;
  }

  private capitalizeFirst(str: string): string {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  private getTotalVariableCount(): number {
    let count = 0;
    for (const vars of this.variableMetadata.values()) {
      count += vars.length;
    }
    return count;
  }

  // Public API
  getAllFileDescriptions(): Array<{category: string, description: string, fileName: string, cycles: string[]}> {
    return Array.from(this.fileMetadata.values()).map(f => ({
      category: f.category,
      description: f.description,
      fileName: f.fileName,
      cycles: f.cycles
    }));
  }

  getVariablesForFile(category: string, fileName: string): VariableMetadata[] {
    const key = `${category}:${fileName}`;
    return this.variableMetadata.get(key) || [];
  }

  getFileCode(category: string, fileName: string): string | null {
    const key = `${category}:${fileName}`;
    const file = this.fileMetadata.get(key);
    return file ? file.fileCode : null;
  }
}

export const metadataLoader = new NHANESMetadataLoader();
