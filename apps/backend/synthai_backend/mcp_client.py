"""
Python MCP client using stdio transport.

Communicates with TypeScript MCP servers via stdin/stdout.
"""

import json
import logging
import subprocess
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with MCP servers via stdio."""

    def __init__(self, server_command: List[str], cwd: Optional[str] = None):
        """
        Initialize MCP client.

        Args:
            server_command: Command to start MCP server (e.g., ["node", "dist/index.js"])
            cwd: Working directory for server process
        """
        self.server_command = server_command
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0

    def start(self) -> None:
        """Start the MCP server process."""
        logger.info(f"Starting MCP server: {' '.join(self.server_command)}")

        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            text=True,
            bufsize=1
        )

        logger.info("MCP server started")

    def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            logger.info("MCP server stopped")

    def _send_request(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send JSON-RPC request to MCP server.

        Args:
            method: JSON-RPC method name
            params: Method parameters

        Returns:
            Response from server
        """
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("MCP server not started")

        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }

        request_json = json.dumps(request) + "\n"
        logger.debug(f"Sending request: {request_json.strip()}")

        self.process.stdin.write(request_json)
        self.process.stdin.flush()

        response_line = self.process.stdout.readline()
        logger.debug(f"Received response: {response_line.strip()}")

        response = json.loads(response_line)

        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        return response.get("result", {})

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from MCP server.

        Returns:
            List of tool definitions
        """
        result = self._send_request("tools/list")
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call an MCP tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        result = self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

        if result.get("isError"):
            error_content = result.get("content", [{}])[0].get("text", "Unknown error")
            raise RuntimeError(f"Tool error: {error_content}")

        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            text = content[0].get("text", "")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        return content

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class NHANESMCPClient(MCPClient):
    """Specialized client for NHANES MCP server."""

    def __init__(self):
        """Initialize NHANES MCP client."""
        project_root = Path(__file__).parent.parent.parent.parent
        nhanes_mcp_dir = project_root / "apps" / "mcp-tools" / "nhanes"

        super().__init__(
            server_command=["node", "dist/index.js"],
            cwd=str(nhanes_mcp_dir)
        )

    def find_files(
        self,
        category: str = "",
        search_term: str = "",
        min_cycle: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Find NHANES data files.

        Args:
            category: Data category (demographics, dietary, examination, laboratory, questionnaire)
            search_term: Search term to filter file descriptions
            min_cycle: Minimum cycle year (e.g., "2013-2014")

        Returns:
            List of matching files with metadata
        """
        return self.call_tool("nhanes_find_files", {
            "category": category,
            "search_term": search_term,
            "min_cycle": min_cycle
        })

    def find_variables(
        self,
        category: str,
        file_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get all variables in a specific NHANES file.

        Args:
            category: Data category
            file_name: File name (description)

        Returns:
            List of variables with descriptions and units
        """
        return self.call_tool("nhanes_find_variables", {
            "category": category,
            "file_name": file_name
        })

    def get_variable_details(
        self,
        category: str,
        file_name: str,
        variable_name: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific variable.

        Args:
            category: Data category
            file_name: File name (description)
            variable_name: NHANES variable name

        Returns:
            Variable details including file code, unit, cycles
        """
        return self.call_tool("nhanes_get_variable_details", {
            "category": category,
            "file_name": file_name,
            "variable_name": variable_name
        })

    def get_download_url(
        self,
        cycle: str,
        file_code: str
    ) -> Dict[str, Any]:
        """
        Get CDC download URL for an NHANES XPT data file.

        Args:
            cycle: NHANES cycle (e.g., "2005-2006", "2017-2018")
            file_code: NHANES file code (e.g., "BMX_D", "LBXHSCRP_J")

        Returns:
            Download URL information including URL, year, exists status
        """
        return self.call_tool("nhanes_get_download_url", {
            "cycle": cycle,
            "file_code": file_code
        })
