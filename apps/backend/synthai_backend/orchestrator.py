"""
Research Orchestrator using single LLM with MCP tools.

Replaces the sequential multi-agent pipeline with a single
orchestrating LLM that uses MCP tools to access NHANES data.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from .config import settings
from .mcp_client import NHANESMCPClient
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """
    Single LLM orchestrator that coordinates research workflow.

    Uses Claude 3.5 Sonnet for higher rate limits and MCP tools for data access.
    """

    def __init__(self):
        """Initialize orchestrator with LLM and MCP clients."""
        self.anthropic_client: Optional[AsyncAnthropic] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        self.nhanes_client: Optional[NHANESMCPClient] = None

        if settings.anthropic_api_key:
            self.anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.provider = "anthropic"
            self.model = "claude-3-haiku-20240307"
            # Claude 3 Haiku rate limits (based on actual API tier)
            self.rate_limiter = RateLimiter(
                max_tokens_per_minute=45000,  # Set to 90% of 50k limit for safety margin
                max_requests_per_minute=50
            )
        elif settings.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            self.provider = "openai"
            self.model = "gpt-4o"
            # GPT-4o rate limits (adjust based on tier)
            self.rate_limiter = RateLimiter(
                max_tokens_per_minute=30000,
                max_requests_per_minute=500
            )
        else:
            raise ValueError("No LLM API key configured")

        logger.info(f"Initialized orchestrator with {self.provider} ({self.model})")

    def start_mcp_clients(self) -> None:
        """Start MCP server processes."""
        self.nhanes_client = NHANESMCPClient()
        self.nhanes_client.start()
        logger.info("Started NHANES MCP client")

    def stop_mcp_clients(self) -> None:
        """Stop MCP server processes."""
        if self.nhanes_client:
            self.nhanes_client.stop()
            self.nhanes_client = None
        logger.info("Stopped MCP clients")

    async def conduct_research(
        self,
        hypothesis: str,
        max_iterations: int = 10
    ) -> Dict[str, Any]:
        """
        Conduct autonomous research for a hypothesis.

        Workflow:
        1. Assess feasibility (is NHANES suitable for this query?)
        2. Search for relevant data files using MCP tools
        3. Identify specific variables needed
        4. Validate variable availability
        5. Return data assembly specification

        Args:
            hypothesis: Research hypothesis or question
            max_iterations: Maximum conversation turns

        Returns:
            Research results with data specifications
        """
        logger.info(f"Starting research for hypothesis: {hypothesis}")

        if not self.nhanes_client:
            raise RuntimeError("MCP clients not started. Call start_mcp_clients() first.")

        # Convert MCP tools to Anthropic/OpenAI tool format
        mcp_tools = self.nhanes_client.list_tools()
        tools = self._convert_mcp_tools_to_llm_format(mcp_tools)

        # Initial system prompt
        system_prompt = self._build_system_prompt()

        # Start conversation
        messages = [
            {
                "role": "user",
                "content": f"""Analyze this research hypothesis and find suitable NHANES data:

Hypothesis: "{hypothesis}"

Please:
1. Assess if NHANES (a US population health survey) is suitable for this hypothesis
2. If suitable, identify which NHANES data files contain relevant variables
3. For each relevant file, identify specific variables needed
4. Validate that variables exist and are available across multiple cycles

If NHANES is NOT suitable (e.g., surgical outcomes, clinical trials, rare diseases), explain why and suggest what type of data source would be more appropriate.

Use the provided tools to search NHANES metadata systematically."""
            }
        ]

        result = {
            "hypothesis": hypothesis,
            "feasible": True,
            "reasoning": "",
            "data_files": [],
            "variables": [],
            "recommended_cycles": [],
            "conversation_history": []
        }

        for iteration in range(max_iterations):
            logger.info(f"Orchestrator iteration {iteration + 1}/{max_iterations}")

            # Estimate tokens for rate limiting
            estimated_tokens = self._estimate_tokens(messages, system_prompt)
            await self.rate_limiter.acquire(estimated_tokens)

            # Call LLM
            if self.provider == "anthropic":
                response = await self._call_anthropic(messages, tools, system_prompt)
            else:
                response = await self._call_openai(messages, tools, system_prompt)

            # Record actual token usage
            actual_tokens = response.get("usage", {}).get("total_tokens", estimated_tokens)
            self.rate_limiter.record_actual_usage(actual_tokens)

            # Add assistant response to conversation
            assistant_message = response["message"]
            messages.append(assistant_message)
            result["conversation_history"].append(assistant_message)

            # Check stop reason
            stop_reason = response.get("stop_reason")

            if stop_reason == "end_turn":
                # LLM finished - extract final answer
                result["reasoning"] = assistant_message.get("content", "")
                break

            elif stop_reason == "tool_use":
                # Process tool calls
                tool_results = await self._execute_tools(assistant_message.get("content", []))

                # Add tool results to conversation (only if non-empty)
                if tool_results:
                    tool_result_message = {
                        "role": "user",
                        "content": tool_results
                    }
                    messages.append(tool_result_message)
                    result["conversation_history"].append(tool_result_message)
                else:
                    logger.warning("No tool results generated despite stop_reason=tool_use")
                    break

            else:
                logger.warning(f"Unexpected stop_reason: {stop_reason}")
                break

        # Extract structured results from conversation
        self._extract_research_results(result)

        logger.info(f"Research completed. Found {len(result['variables'])} variables across {len(result['data_files'])} files")

        return result

    def _build_system_prompt(self) -> str:
        """Build system prompt for orchestrator."""
        return """You are a medical research assistant specializing in NHANES (National Health and Nutrition Examination Survey) data analysis.

NHANES is a US population health survey that includes:
- Demographics (age, sex, race, income, education)
- Dietary intake (food frequency, 24-hour recall)
- Physical examinations (blood pressure, BMI, body measurements)
- Laboratory tests (blood chemistry, infectious disease markers, environmental exposures)
- Questionnaires (medical history, health behaviors, quality of life)

NHANES does NOT include:
- Surgical outcomes or clinical trial data
- Rare diseases (sample sizes too small)
- Detailed medical imaging
- Long-term longitudinal follow-up (beyond mortality)
- Non-US populations

Your task:
1. Assess if the research hypothesis is suitable for NHANES
2. If suitable, systematically search for relevant data files
3. Identify specific variables needed for the analysis
4. Validate variable availability across multiple cycles (2009-2018)

Use the provided tools to search NHANES metadata. Be thorough and precise."""

    def _convert_mcp_tools_to_llm_format(self, mcp_tools: List[Dict]) -> List[Dict]:
        """Convert MCP tool definitions to Anthropic/OpenAI format."""
        converted = []

        for tool in mcp_tools:
            converted.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["inputSchema"]
            })

        return converted

    def _estimate_tokens(self, messages: List[Dict], system_prompt: str) -> int:
        """Estimate token count for rate limiting."""
        # Rough estimate: 4 characters per token
        text = system_prompt
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                text += content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text += json.dumps(item)

        return len(text) // 4

    async def _call_anthropic(
        self,
        messages: List[Dict],
        tools: List[Dict],
        system_prompt: str
    ) -> Dict[str, Any]:
        """Call Anthropic API."""
        response = await self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.0,
            system=system_prompt,
            messages=messages,
            tools=tools
        )

        # Serialize ContentBlock objects to dicts
        content = []
        for block in response.content:
            if block.type == "text":
                content.append({
                    "type": "text",
                    "text": block.text
                })
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })

        return {
            "message": {
                "role": "assistant",
                "content": content
            },
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }

    async def _call_openai(
        self,
        messages: List[Dict],
        tools: List[Dict],
        system_prompt: str
    ) -> Dict[str, Any]:
        """Call OpenAI API."""
        # Insert system prompt as first message
        messages_with_system = [
            {"role": "system", "content": system_prompt},
            *messages
        ]

        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages_with_system,
            tools=[{"type": "function", "function": t} for t in tools],
            temperature=0.0
        )

        message = response.choices[0].message

        return {
            "message": {
                "role": "assistant",
                "content": message.tool_calls if message.tool_calls else message.content
            },
            "stop_reason": "tool_use" if message.tool_calls else "end_turn",
            "usage": {
                "total_tokens": response.usage.total_tokens
            }
        }

    async def _execute_tools(self, content: List[Dict]) -> List[Dict]:
        """
        Execute tool calls and return results.

        Args:
            content: Assistant message content with tool_use blocks

        Returns:
            Tool result blocks
        """
        tool_results = []

        logger.info(f"_execute_tools called with content: {json.dumps(content, indent=2)}")

        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_name = block["name"]
                tool_input = block["input"]
                tool_use_id = block["id"]

                logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

                try:
                    # Call MCP tool
                    if self.nhanes_client and tool_name.startswith("nhanes_"):
                        result = self.nhanes_client.call_tool(tool_name, tool_input)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result) if not isinstance(result, str) else result
                    })

                except Exception as e:
                    logger.error(f"Tool execution failed: {e}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True
                    })

        return tool_results

    def _extract_research_results(self, result: Dict[str, Any]) -> None:
        """
        Extract structured research results from conversation history.

        Updates result dict in-place with extracted data.
        """
        # Parse conversation history to extract files, variables, cycles
        for message in result["conversation_history"]:
            content = message.get("content", [])

            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_content = block.get("content", "")

                        try:
                            data = json.loads(tool_content) if isinstance(tool_content, str) else tool_content

                            # Extract files
                            if isinstance(data, list) and data and "file_name" in data[0]:
                                for file_info in data:
                                    if file_info not in result["data_files"]:
                                        result["data_files"].append(file_info)

                            # Extract variables
                            if isinstance(data, list) and data and "variable_name" in data[0]:
                                for var_info in data:
                                    if var_info not in result["variables"]:
                                        result["variables"].append(var_info)

                            # Extract variable details
                            if isinstance(data, dict) and "variable_name" in data:
                                if data not in result["variables"]:
                                    result["variables"].append(data)
                                if data.get("cycles"):
                                    for cycle in data["cycles"]:
                                        if cycle not in result["recommended_cycles"]:
                                            result["recommended_cycles"].append(cycle)

                        except (json.JSONDecodeError, TypeError):
                            pass

        # Sort cycles
        result["recommended_cycles"].sort(reverse=True)

    def __enter__(self):
        """Context manager entry."""
        self.start_mcp_clients()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_mcp_clients()
