#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { metadataLoader } from './metadata-loader.js';

const server = new Server(
  {
    name: 'nhanes-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

const tools: Tool[] = [
  {
    name: 'nhanes_find_files',
    description: 'Search NHANES data files by category and description. Returns all available data files that match the criteria. Use this first to identify which files contain relevant health data.',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: 'Data category: demographics, dietary, examination, laboratory, or questionnaire. Leave empty to search all categories.',
          enum: ['demographics', 'dietary', 'examination', 'laboratory', 'questionnaire', ''],
        },
        search_term: {
          type: 'string',
          description: 'Optional search term to filter file descriptions (case-insensitive)',
        },
        min_cycle: {
          type: 'string',
          description: 'Minimum cycle year (e.g., "2013-2014"). Only returns files available in this cycle or later.',
        },
      },
    },
  },
  {
    name: 'nhanes_find_variables',
    description: 'Get all variables in a specific NHANES data file. Use this after finding relevant files to see what specific measurements are available.',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: 'Data category: demographics, dietary, examination, laboratory, or questionnaire',
          enum: ['demographics', 'dietary', 'examination', 'laboratory', 'questionnaire'],
        },
        file_name: {
          type: 'string',
          description: 'Exact file name (description) from nhanes_find_files result',
        },
      },
      required: ['category', 'file_name'],
    },
  },
  {
    name: 'nhanes_get_variable_details',
    description: 'Get detailed information about a specific variable including its NHANES code, description, unit, and which cycles it appears in.',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: 'Data category',
          enum: ['demographics', 'dietary', 'examination', 'laboratory', 'questionnaire'],
        },
        file_name: {
          type: 'string',
          description: 'File name (description)',
        },
        variable_name: {
          type: 'string',
          description: 'NHANES variable name (e.g., LBXHSCRP)',
        },
      },
      required: ['category', 'file_name', 'variable_name'],
    },
  },
  {
    name: 'nhanes_get_download_url',
    description: 'Get the CDC download URL for an NHANES XPT data file. Returns the direct download URL and validates it exists.',
    inputSchema: {
      type: 'object',
      properties: {
        cycle: {
          type: 'string',
          description: 'NHANES cycle (e.g., "2005-2006", "2017-2018")',
        },
        file_code: {
          type: 'string',
          description: 'NHANES file code from metadata (e.g., "BMX_D", "LBXHSCRP_J")',
        },
      },
      required: ['cycle', 'file_code'],
    },
  },
];

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools };
});

// Track if metadata has been loaded
let metadataLoaded = false;

async function ensureMetadataLoaded(): Promise<void> {
  if (!metadataLoaded) {
    console.error('Loading NHANES metadata on-demand...');
    await metadataLoader.loadAllMetadata();
    metadataLoaded = true;
    console.error('Metadata loaded successfully');
  }
}

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'nhanes_find_files': {
        await ensureMetadataLoaded();

        const category = (args?.category as string) || '';
        const searchTerm = (args?.search_term as string) || '';
        const minCycle = (args?.min_cycle as string) || '';

        const allFiles = metadataLoader.getAllFileDescriptions();

        let filtered = allFiles;

        if (category) {
          filtered = filtered.filter(f => f.category === category);
        }

        if (searchTerm) {
          const term = searchTerm.toLowerCase();
          filtered = filtered.filter(f =>
            f.description.toLowerCase().includes(term) ||
            f.fileName.toLowerCase().includes(term)
          );
        }

        if (minCycle) {
          filtered = filtered.filter(f =>
            f.cycles.some(cycle => cycle >= minCycle)
          );
        }

        const result = filtered.map(f => ({
          category: f.category,
          file_name: f.fileName,
          description: f.description,
          cycles: f.cycles,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'nhanes_find_variables': {
        await ensureMetadataLoaded();

        const category = args?.category as string;
        const fileName = args?.file_name as string;

        if (!category || !fileName) {
          throw new Error('category and file_name are required');
        }

        const variables = metadataLoader.getVariablesForFile(category, fileName);

        const result = variables.map(v => ({
          variable_name: v.variableName,
          description: v.description,
          unit: v.unit,
          cycles: v.cycles,
        }));

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'nhanes_get_variable_details': {
        await ensureMetadataLoaded();

        const category = args?.category as string;
        const fileName = args?.file_name as string;
        const variableName = args?.variable_name as string;

        if (!category || !fileName || !variableName) {
          throw new Error('category, file_name, and variable_name are required');
        }

        const variables = metadataLoader.getVariablesForFile(category, fileName);
        const variable = variables.find(v => v.variableName === variableName);

        if (!variable) {
          throw new Error(`Variable ${variableName} not found in ${category}/${fileName}`);
        }

        const fileCode = metadataLoader.getFileCode(category, fileName);

        const result = {
          variable_name: variable.variableName,
          description: variable.description,
          file_name: variable.fileName,
          file_code: fileCode,
          category: variable.category,
          unit: variable.unit,
          cycles: variable.cycles,
        };

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'nhanes_get_download_url': {
        const cycle = args?.cycle as string;
        const fileCode = args?.file_code as string;

        if (!cycle || !fileCode) {
          throw new Error('cycle and file_code are required');
        }

        // Extract start year from cycle (e.g., "2005-2006" -> "2005")
        const year = cycle.split('-')[0];

        // Build CDC download URL
        // Format: https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{FILE_CODE}.XPT
        const downloadUrl = `https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/${year}/DataFiles/${fileCode}.XPT`;

        // Validate URL exists with HEAD request
        const fetch = (await import('node-fetch')).default;
        try {
          const response = await fetch(downloadUrl, { method: 'HEAD' });
          const exists = response.ok;

          const result = {
            download_url: downloadUrl,
            file_code: fileCode,
            cycle: cycle,
            year: year,
            exists: exists,
            status_code: response.status
          };

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(result, null, 2),
              },
            ],
          };
        } catch (error: any) {
          throw new Error(`Failed to validate URL: ${error.message}`);
        }
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({ error: error.message }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

async function main() {
  console.error('NHANES MCP server starting...');
  console.error('Metadata will be loaded on first use');

  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('NHANES MCP server ready');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
