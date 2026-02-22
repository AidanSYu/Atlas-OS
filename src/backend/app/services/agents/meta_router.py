"""
Meta-Router Agent.
Responsible for intent classification and model orchestration.
"""
import logging
from typing import List, Optional
from app.services.llm import LLMService

logger = logging.getLogger(__name__)

async def route_intent(query: str, llm_service: LLMService) -> str:
    """Classify query into one of four agent types.

    SIMPLE         - Direct fact lookup, specific question about a document
    DEEP_DISCOVERY - Synthesis, connection-finding, hypothesis generation
    BROAD_RESEARCH - Survey, landscape scan, comparison across many sources
    MULTI_STEP     - Complex query requiring both deep and broad analysis
    """
    prompt = f"""Classify this research query into exactly ONE category:

SIMPLE - The user wants a specific fact, quote, or detail from their documents.
Examples: "What methodology did they use?", "What is the sample size in Table 2?"

DEEP_DISCOVERY - The user wants to find hidden connections, synthesize across domains,
generate hypotheses, or discover relationships.
Examples: "How might X relate to Y?", "What connections exist between these papers?"

BROAD_RESEARCH - The user wants a broad survey, comparison, or landscape overview.
Examples: "Compare the methods across all papers", "What approaches exist for X?"

MULTI_STEP - The query requires BOTH deep analysis AND broad comparison, or has
multiple distinct sub-questions that need different approaches.
Examples: "Find connections between X and Y, then compare with alternative approaches"

Query: {query}

Respond with ONLY the category name:"""

    try:
        response = await llm_service.generate(prompt=prompt, temperature=0.0, max_tokens=20)
        response = response.strip().upper()
        
        valid_intents = ["SIMPLE", "DEEP_DISCOVERY", "BROAD_RESEARCH", "MULTI_STEP"]
        # Basic parsing
        for intent in valid_intents:
            if intent in response:
                return intent
                
        return "DEEP_DISCOVERY" # Default fallback
    except Exception as e:
        logger.warning(f"Router classification failed: {e}, defaulting to DEEP_DISCOVERY")
        return "DEEP_DISCOVERY"

async def ensure_optimal_model(intent: str, llm_service: LLMService) -> None:
    """Swap to the optimal local model for the task if needed.

    Skips model swapping when an API model is active — the user explicitly
    chose a cloud model and we should not override that with a local GGUF.
    """
    try:
        # Never override the user's API model choice
        if getattr(llm_service, "_model_source", "local") == "api":
            logger.debug("Skipping model swap: API model is active")
            return

        available = llm_service.list_available_models()
        current = llm_service.active_model_name

        if not available:
            return

        # Define model preferences per intent
        # These partial matches correspond to common model filenames
        DEEP_MODELS = ["deepseek", "qwen2.5-7b", "llama-3-8b", "llama-3.1-8b", "mistral-7b"]
        FAST_MODELS = ["phi-3", "qwen2.5-3b", "llama-3.2-3b", "gemma-2b"]

        target_model = None

        if intent in ("DEEP_DISCOVERY", "BROAD_RESEARCH", "MULTI_STEP"):
            # Prefer a larger/smarter model
            for preferred in DEEP_MODELS:
                match = next((m for m in available if preferred.lower() in m.lower()), None)
                if match:
                    target_model = match
                    break
        elif intent == "SIMPLE":
            # Prefer a faster/smaller model
            for preferred in FAST_MODELS:
                match = next((m for m in available if preferred.lower() in m.lower()), None)
                if match:
                    target_model = match
                    break
        
        # If we found a better model and it's not the current one, swap
        if target_model and target_model != current:
            logger.info(f"Meta-Router: Swapping to optimal model for {intent}: {target_model}")
            await llm_service.load_model(target_model)
            
    except Exception as e:
        logger.error(f"Model swapping failed: {e}")
