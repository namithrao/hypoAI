#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import { PhysioNetClient } from './physionet-client.js';
import {
  PhysioNetCatalogSchema,
  PhysioNetFetchSchema,
  PhysioNetCatalogQuery,
  PhysioNetFetchQuery
} from './types.js';

class PhysioNetMCPServer {
  private server: Server;
  private physionetClient: PhysioNetClient;

  constructor() {
    this.server = new Server(
      {
        name: 'physionet-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.physionetClient = new PhysioNetClient(process.env.PHYSIONET_CACHE_DIR);
    this.setupToolHandlers();
  }

  private setupToolHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'physionet_catalog',
            description: 'Search PhysioNet dataset catalog for biomedical datasets',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'Search query for dataset titles, descriptions, or tags',
                  default: ''
                },
                category: {
                  type: 'string',
                  enum: ['ecg', 'eeg', 'emg', 'clinical', 'waveform', 'annotation', 'all'],
                  description: 'Filter by dataset category',
                  default: 'all'
                },
                limit: {
                  type: 'integer',
                  description: 'Maximum number of datasets to return',
                  default: 50,
                  minimum: 1
                },
                offset: {
                  type: 'integer',
                  description: 'Number of datasets to skip for pagination',
                  default: 0,
                  minimum: 0
                },
                dry_run: {
                  type: 'boolean',
                  description: 'If true, return only metadata and estimated count',
                  default: false
                }
              }
            }
          },
          {
            name: 'physionet_fetch',
            description: 'Fetch data from a specific PhysioNet dataset (allowlisted datasets only)',
            inputSchema: {
              type: 'object',
              properties: {
                dataset: {
                  type: 'string',
                  description: 'Dataset ID (slug) from PhysioNet catalog'
                },
                files: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Specific files to fetch from the dataset. If empty, fetches all data files',
                  default: []
                },
                columns: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Specific columns/signals to retrieve. If empty, returns all columns',
                  default: []
                },
                limit: {
                  type: 'integer',
                  description: 'Maximum number of data rows to return',
                  default: 10000,
                  minimum: 1
                },
                offset: {
                  type: 'integer',
                  description: 'Number of rows to skip for pagination',
                  default: 0,
                  minimum: 0
                },
                dry_run: {
                  type: 'boolean',
                  description: 'If true, return only metadata and estimated row count',
                  default: false
                }
              },
              required: ['dataset']
            }
          }
        ]
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        if (name === 'physionet_catalog') {
          // Validate arguments
          const query = PhysioNetCatalogSchema.parse(args) as PhysioNetCatalogQuery;

          // Execute catalog search
          const result = await this.physionetClient.catalog(query);

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(result, null, 2)
              }
            ]
          };
        } else if (name === 'physionet_fetch') {
          // Validate arguments
          const query = PhysioNetFetchSchema.parse(args) as PhysioNetFetchQuery;

          // Execute data fetch
          const result = await this.physionetClient.fetch(query);

          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(result, null, 2)
              }
            ]
          };
        } else {
          throw new McpError(
            ErrorCode.MethodNotFound,
            `Unknown tool: ${name}`
          );
        }
      } catch (error) {
        if (error instanceof McpError) {
          throw error;
        }

        const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
        throw new McpError(
          ErrorCode.InternalError,
          `Tool execution failed: ${errorMessage}`
        );
      }
    });
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('PhysioNet MCP server running on stdio');
  }
}

// Run the server
if (require.main === module) {
  const server = new PhysioNetMCPServer();
  server.run().catch(console.error);
}

export { PhysioNetMCPServer };