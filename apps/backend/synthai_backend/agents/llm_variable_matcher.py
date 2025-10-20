"""
LLM-powered variable matching with zero hardcoded knowledge.
Uses semantic reasoning over actual NHANES metadata.
"""

import json
import logging
from typing import List, Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from .nhanes_metadata_fetcher import VariableMetadata

logger = logging.getLogger(__name__)


class LLMVariableMatcher:
    """
    Uses LLM to match conceptual variables to NHANES variables.
    NO hardcoded knowledge about variable naming, medical terminology, or units.
    """

    def __init__(
        self,
        anthropic_client: Optional[AsyncAnthropic] = None,
        openai_client: Optional[AsyncOpenAI] = None
    ):
        self.anthropic_client = anthropic_client
        self.openai_client = openai_client
        self.provider = "anthropic" if anthropic_client else "openai"

    async def find_best_match(
        self,
        concept: str,
        candidates: List[VariableMetadata],
        expected_unit: Optional[str] = None,
        context: Optional[str] = None
    ) -> Optional[VariableMetadata]:
        """
        Use LLM to find best matching NHANES variable for a concept.

        Args:
            concept: Conceptual variable name (e.g., "CRP", "blood pressure")
            candidates: List of potential NHANES variables
            expected_unit: Expected unit of measurement (from literature)
            context: Additional context (e.g., from research hypothesis)

        Returns:
            Best matching VariableMetadata or None
        """

        if not candidates:
            return None

        if len(candidates) == 1:
            # Only one option, verify it's reasonable
            is_match = await self._verify_single_candidate(
                concept, candidates[0], expected_unit
            )
            return candidates[0] if is_match else None

        # Multiple candidates - ask LLM to select best
        candidates_text = "\n".join([
            f"{i+1}. Variable: {c.variable_name}\n"
            f"   Description: {c.variable_description}\n"
            f"   File: {c.data_file_description}\n"
            f"   Unit: {c.unit or 'unknown'}\n"
            f"   Source: {c.source}"
            for i, c in enumerate(candidates)
        ])

        prompt = f"""You are analyzing NHANES (National Health and Nutrition Examination Survey) variable metadata.

Research Variable: "{concept}"
Expected Unit: {expected_unit or 'unknown'}
{f'Context: {context}' if context else ''}

Available NHANES Variables:
{candidates_text}

Task: Which variable (if any) is the PRIMARY MEASUREMENT for "{concept}"?

Selection Criteria:
1. Semantic match - Does the description match the concept meaning?
2. Unit compatibility - Does the unit match expectations?
3. Variable purpose - Is this a measurement (not a comment/quality code)?
4. Data quality - Prefer variables from reliable sources (html_scraper > api > pytool)

Important:
- Focus on the variable DESCRIPTION, not just the variable NAME
- Some variables are comments/flags (e.g., "Comment Code") - avoid these
- If multiple measurement variables exist, choose the most direct one
- If no clear match exists, select null

Return JSON:
{{
  "selected_index": <1-{len(candidates)} or null>,
  "confidence": <"high", "medium", "low">,
  "reasoning": "<brief explanation>"
}}

Answer:"""

        try:
            if self.provider == "anthropic":
                response = await self._call_anthropic(prompt)
            else:
                response = await self._call_openai(prompt)

            result = json.loads(response)

            if result['selected_index'] is None:
                logger.info(
                    f"LLM found no match for '{concept}' "
                    f"(reasoning: {result['reasoning']})"
                )
                return None

            selected = candidates[result['selected_index'] - 1]
            logger.info(
                f"LLM matched '{concept}' → {selected.variable_name} "
                f"(confidence: {result['confidence']}, "
                f"reasoning: {result['reasoning']})"
            )

            return selected

        except Exception as e:
            logger.error(f"LLM matching failed: {e}")
            # Fallback to first candidate
            logger.warning(f"Falling back to first candidate: {candidates[0].variable_name}")
            return candidates[0]

    async def _verify_single_candidate(
        self,
        concept: str,
        candidate: VariableMetadata,
        expected_unit: Optional[str]
    ) -> bool:
        """Verify a single candidate is a reasonable match."""

        prompt = f"""Is this NHANES variable a reasonable match for the research concept?

Research Concept: "{concept}"
Expected Unit: {expected_unit or 'unknown'}

NHANES Variable:
- Name: {candidate.variable_name}
- Description: {candidate.variable_description}
- Unit: {candidate.unit or 'unknown'}
- File: {candidate.data_file_description}

Does this variable measure or represent "{concept}"?

Guidelines:
- Check if the description semantically matches the concept
- Verify unit compatibility if unit is specified
- Avoid comment codes or quality flags
- Consider if this is a direct measurement

Return JSON:
{{"is_match": <true or false>, "reasoning": "<brief explanation>"}}

Answer:"""

        try:
            if self.provider == "anthropic":
                response = await self._call_anthropic(prompt)
            else:
                response = await self._call_openai(prompt)

            result = json.loads(response)

            if result['is_match']:
                logger.info(
                    f"Verified '{concept}' → {candidate.variable_name} "
                    f"(reasoning: {result['reasoning']})"
                )
            else:
                logger.info(
                    f"Rejected '{concept}' → {candidate.variable_name} "
                    f"(reasoning: {result['reasoning']})"
                )

            return result['is_match']

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            # Fallback to accepting the candidate
            return True

    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        message = await self.anthropic_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
