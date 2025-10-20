"""
SynthAI Backend - MCP-Based Research System

FastAPI application with single orchestrator endpoint using MCP tools.
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Request/Response models
class HypothesisRequest(BaseModel):
    hypothesis: str = Field(..., min_length=10, max_length=1000,
                           description="Research hypothesis or question")
    max_iterations: int = Field(default=10, ge=1, le=20,
                                description="Maximum LLM conversation turns")


class ResearchResponse(BaseModel):
    """Response from autonomous research orchestrator."""
    success: bool
    hypothesis: str
    feasible: bool
    reasoning: str = ""
    data_files: list[Dict[str, Any]] = Field(default_factory=list)
    variables: list[Dict[str, Any]] = Field(default_factory=list)
    recommended_cycles: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Global orchestrator instance
orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize orchestrator on startup, cleanup on shutdown."""
    global orchestrator

    logger.info("Initializing SynthAI MCP Orchestrator...")

    try:
        from .orchestrator import ResearchOrchestrator
        orchestrator = ResearchOrchestrator()
        orchestrator.start_mcp_clients()
        logger.info("MCP Orchestrator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        raise

    yield

    # Cleanup
    if orchestrator:
        orchestrator.stop_mcp_clients()
    logger.info("Orchestrator cleaned up")


# Create FastAPI app
app = FastAPI(
    title="SynthAI MCP Research System",
    description="AI-powered medical research using MCP tools and NHANES data",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "SynthAI MCP Research System",
        "version": "2.0.0",
        "orchestrator_enabled": orchestrator is not None,
        "api_configured": settings.has_ai_provider
    }


@app.post("/api/research", response_model=ResearchResponse)
async def conduct_research(request: HypothesisRequest):
    """
    Autonomous research using single orchestrator LLM with MCP tools.

    This endpoint:
    1. Assesses hypothesis feasibility for NHANES data
    2. Searches for relevant data files using MCP tools
    3. Identifies specific variables needed
    4. Validates variable availability across cycles

    Returns structured research results with data specifications.
    """
    try:
        if not orchestrator:
            raise HTTPException(
                status_code=503,
                detail="Orchestrator not initialized. Check server logs."
            )

        logger.info(f"Starting research: {request.hypothesis}")

        # Conduct research
        result = await orchestrator.conduct_research(
            hypothesis=request.hypothesis,
            max_iterations=request.max_iterations
        )

        # Extract reasoning text from content blocks
        reasoning_text = ""
        reasoning_data = result.get("reasoning", "")
        if isinstance(reasoning_data, list):
            # Extract text from content blocks
            text_parts = []
            for block in reasoning_data:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            reasoning_text = "\n\n".join(text_parts)
        elif isinstance(reasoning_data, str):
            reasoning_text = reasoning_data
        else:
            reasoning_text = str(reasoning_data)

        # Build warnings
        warnings = []
        if not result["feasible"]:
            warnings.append("NHANES may not be suitable for this hypothesis. Consider alternative data sources.")

        if len(result["variables"]) == 0 and result["feasible"]:
            warnings.append("No variables found despite hypothesis being feasible. May need manual specification.")

        if len(result["data_files"]) > 10:
            warnings.append(f"Found {len(result['data_files'])} data files - consider narrowing the hypothesis.")

        return ResearchResponse(
            success=result["feasible"],
            hypothesis=result["hypothesis"],
            feasible=result["feasible"],
            reasoning=reasoning_text,
            data_files=result["data_files"],
            variables=result["variables"],
            recommended_cycles=result["recommended_cycles"],
            warnings=warnings,
            metadata={
                "num_files": len(result["data_files"]),
                "num_variables": len(result["variables"]),
                "num_cycles": len(result["recommended_cycles"]),
                "conversation_turns": len(result.get("conversation_history", []))
            }
        )

    except Exception as e:
        logger.error(f"Research failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Research failed: {str(e)}"
        )


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "orchestrator": "running" if orchestrator else "not initialized",
        "mcp_server": "connected" if orchestrator and orchestrator.nhanes_client else "disconnected",
        "llm_provider": orchestrator.provider if orchestrator else None,
        "llm_model": orchestrator.model if orchestrator else None,
    }


# New Multi-Agent Literature Endpoint
class LiteratureRequest(BaseModel):
    question: str = Field(..., min_length=10, max_length=1000)
    max_papers: int = Field(default=5, ge=1, le=20)


@app.post("/api/literature")
async def analyze_literature(request: LiteratureRequest):
    """
    Literature discovery using new multi-agent system.

    Searches PubMed, analyzes papers, finds genes/variants, generates hypotheses.
    """
    try:
        logger.info(f"Literature analysis: {request.question}")

        # Import here to avoid issues if not yet initialized
        from anthropic import AsyncAnthropic
        from .agents.literature_agent import LiteratureDiscoveryAgent

        # Create clients
        if not settings.anthropic_api_key:
            raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")

        anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        # Create agent (using orchestrator's MCP client if available)
        mcp_client = orchestrator.nhanes_client if orchestrator else None

        agent = LiteratureDiscoveryAgent(
            ncbi_client=mcp_client,
            anthropic_client=anthropic_client,
        )

        # Run analysis
        results = await agent.analyze(
            hypothesis=request.question,
            max_papers=request.max_papers
        )

        return {
            "success": True,
            "papers_analyzed": results.get('papers_analyzed', 0),
            "variables_found": results.get('all_variables', []),
            "genes_found": results.get('all_genes', []),
            "variants_found": results.get('all_variants', []),
            "novel_hypotheses": results.get('synthesis', {}).get('novel_hypotheses', []),
            "patterns": results.get('synthesis', {}).get('patterns', []),
            "research_gaps": results.get('synthesis', {}).get('research_gaps', []),
        }

    except Exception as e:
        logger.error(f"Literature analysis failed: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "papers_analyzed": 0,
            "variables_found": [],
            "genes_found": [],
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
