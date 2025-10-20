#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import { SeerClient } from './seer-client.js';
import { SeerQuerySchema, SeerQuery } from './types.js';

class SeerMCPServer {
  private server: Server;
  private seerClient: SeerClient;

  constructor() {
    this.server = new Server(
      {
        name: 'seer-mcp-server',
        version: '1.0.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.seerClient = new SeerClient(
      process.env.SEER_CACHE_DIR,
      process.env.SEER_API_KEY
    );
    this.setupToolHandlers();
  }

  private setupToolHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'seer_query',
            description: 'Query SEER (Surveillance, Epidemiology, and End Results) cancer registry data',
            inputSchema: {
              type: 'object',
              properties: {
                endpoint: {
                  type: 'string',
                  enum: ['incidence', 'mortality', 'survival', 'population', 'sites', 'demographics'],
                  description: 'SEER data endpoint to query'
                },
                params: {
                  type: 'object',
                  description: 'Query parameters specific to the endpoint',
                  additionalProperties: true,
                  default: {}
                },
                limit: {
                  type: 'integer',
                  description: 'Maximum number of records to return',
                  default: 10000,
                  minimum: 1
                },
                offset: {
                  type: 'integer',
                  description: 'Number of records to skip for pagination',
                  default: 0,
                  minimum: 0
                },
                dry_run: {
                  type: 'boolean',
                  description: 'If true, return only metadata and estimated record count',
                  default: false
                }
              },
              required: ['endpoint']
            }
          }
        ]
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        if (name === 'seer_query') {
          // Validate arguments
          const query = SeerQuerySchema.parse(args) as SeerQuery;

          // Execute query
          const result = await this.seerClient.query(query);

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
    console.error('SEER MCP server running on stdio');
  }
}

// Run the server
if (require.main === module) {
  const server = new SeerMCPServer();
  server.run().catch(console.error);
}

export { SeerMCPServer };