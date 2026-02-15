"""
Prompt Template Library for Atlas 2.0 (Phase A3).

Provides structured prompts with few-shot examples for improved LLM performance.
Based on SOTA 2026 agentic RAG patterns (DeepSeek R1, MiniMax efficient reasoning).
"""
from typing import Dict, Any, Optional


class PromptTemplate:
    """Base class for structured prompts with few-shot examples."""

    def __init__(
        self,
        template: str,
        examples: str = "",
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ):
        """
        Initialize a prompt template.

        Args:
            template: The prompt template with {placeholders}
            examples: Optional few-shot examples to prepend
            temperature: Recommended temperature for this prompt
            max_tokens: Recommended max tokens for response
        """
        self.template = template
        self.examples = examples
        self.temperature = temperature
        self.max_tokens = max_tokens

    def format(self, **kwargs) -> str:
        """Format the prompt with given kwargs.

        If examples are provided, they are prepended with a separator.
        """
        formatted_template = self.template.format(**kwargs)

        if self.examples:
            return f"{self.examples}\n\n---\n\nNOW YOUR TURN:\n\n{formatted_template}"

        return formatted_template


# ============================================================
# NAVIGATOR 2.0 PROMPTS
# ============================================================

NAVIGATOR_PLANNER = PromptTemplate(
    template="""You are a research planning agent. Analyze this query step-by-step:

USER QUERY: {query}

Think through:
1. What is the user REALLY asking? (rephrase in clear terms)
2. What types of information do we need to answer this?
3. What entities or concepts should we look for in the knowledge graph?
4. What potential gaps or ambiguities might exist in our knowledge base?

Return your analysis as JSON:
{{
  "understanding": "Your clear interpretation of what the user wants",
  "information_needs": ["type 1: description", "type 2: description"],
  "search_terms": ["search term 1", "search term 2", "search term 3"],
  "potential_gaps": ["potential gap 1", "potential gap 2"]
}}
""",
    examples="""EXAMPLE 1:
Query: "How does polymer X relate to drug delivery?"

Good Response:
```json
{{
  "understanding": "User wants to understand the connection between polymer X's properties and its application in drug delivery systems",
  "information_needs": [
    "Chemical properties of polymer X",
    "Drug delivery mechanisms",
    "Studies linking polymer X to drug delivery"
  ],
  "search_terms": [
    "polymer X drug delivery",
    "polymer X biocompatibility",
    "controlled release polymers"
  ],
  "potential_gaps": [
    "Specific clinical trials",
    "FDA approval status"
  ]
}}
```

Bad Response (avoid):
```json
{{
  "understanding": "polymer X",
  "information_needs": ["information"],
  "search_terms": ["polymer X"],
  "potential_gaps": []
}}
```
(Too vague, not actionable)
""",
    temperature=0.1,
    max_tokens=1024,
)


NAVIGATOR_REASONER = PromptTemplate(
    template="""You are a research synthesis agent with deep analytical capabilities.

USER QUERY: {query}

EVIDENCE FROM DOCUMENTS:
{evidence}

KNOWLEDGE GRAPH STRUCTURE:
{graph}

FORMAT YOUR RESPONSE WITH EXPLICIT REASONING:

<thinking>
Wait, let me think through this carefully...

Step 1: What does the evidence actually tell us?
[Analyze the evidence systematically...]

Step 2: How does this connect to the query?
[Make explicit connections...]

Step 3: Are there any contradictions or gaps in the evidence?
[Self-check your reasoning...]

Step 4: What can we confidently conclude?
[Synthesize your findings...]
</thinking>

<hypothesis>
[Your clear, evidence-based answer to the query. Include specific citations like: "According to [Source.pdf, p.X], ..."]
</hypothesis>

<evidence_mapping>
Claim 1: [specific claim] → Evidence: [Source.pdf, p.X]
Claim 2: [specific claim] → Evidence: [Source.pdf, p.Y]
...
</evidence_mapping>

<confidence>HIGH/MEDIUM/LOW because [brief justification]</confidence>

CRITICAL: If evidence is insufficient, explicitly state "I cannot find sufficient evidence for [specific aspect]."
""",
    examples="""EXAMPLE:
Query: "How does polymer X relate to drug delivery?"

Evidence: 
[Source: Smith2023.pdf, Page 5]
Polymer X exhibits hydrophilic properties with a molecular weight of 50kDa...

[Source: Jones2022.pdf, Page 12]
Hydrophilic polymers enable controlled drug release through swelling mechanisms...

Good Response:
<thinking>
Wait, let me think through this carefully...

Step 1: What does the evidence tell us?
- Smith2023 confirms polymer X is hydrophilic (p.5)
- Jones2022 explains hydrophilic polymers enable controlled release (p.12)

Step 2: How does this connect to the query?
The hydrophilic nature of polymer X directly relates to drug delivery because it enables the controlled release mechanism described by Jones2022.

Step 3: Are there any contradictions or gaps?
No contradictions. Gap: No specific studies of polymer X in drug delivery applications mentioned.

Step 4: What can we confidently conclude?
Polymer X's hydrophilic properties make it suitable for controlled drug release, though direct studies are not cited.
</thinking>

<hypothesis>
Polymer X shows promise for drug delivery systems due to its hydrophilic backbone structure (molecular weight 50kDa, Smith2023, p.5). Hydrophilic polymers like polymer X enable controlled drug release through swelling-based mechanisms (Jones2022, p.12), suggesting it could be effective for sustained release applications.
</hypothesis>

<evidence_mapping>
Claim 1: Polymer X is hydrophilic → Evidence: [Smith2023.pdf, p.5]
Claim 2: Hydrophilic polymers enable controlled release → Evidence: [Jones2022.pdf, p.12]
</evidence_mapping>

<confidence>MEDIUM because properties support application, but no direct polymer X drug delivery studies cited</confidence>

Bad Response (avoid):
"Polymer X is used in drug delivery." 
(No reasoning, no citations, vague)
""",
    temperature=0.2,
    max_tokens=2048,
)


NAVIGATOR_CRITIC = PromptTemplate(
    template="""You are a critical reviewer. Your job is to find flaws, gaps, and contradictions.

ORIGINAL QUERY: {query}

GENERATED HYPOTHESIS:
{hypothesis}

EVIDENCE USED:
{evidence_map}

CRITICAL ANALYSIS:

1. COVERAGE: Does the hypothesis answer ALL parts of the query? What's missing?
2. CONTRADICTIONS: Do any evidence sources contradict each other?
3. EVIDENCE GAPS: Which claims lack supporting evidence?
4. CLARITY: Is the answer clear and well-structured?

Based on your analysis, return JSON:
{{
  "verdict": "PASS" | "REFINE" | "RETRIEVE_MORE",
  "issues_found": ["issue 1", "issue 2"],
  "missing_aspects": ["aspect 1", "aspect 2"],
  "contradictions": ["contradiction 1"],
  "confidence_assessment": "HIGH" | "MEDIUM" | "LOW"
}}

PASS = Hypothesis is well-supported and complete
REFINE = Minor issues, can fix with current evidence
RETRIEVE_MORE = Major gaps, need additional evidence
""",
    examples="""EXAMPLE:
Query: "What is the drug release efficiency of polymer X?"
Hypothesis: "Polymer X is hydrophilic and suitable for drug delivery."
Evidence: Only structural properties cited, no efficiency data.

Good Response:
```json
{{
  "verdict": "RETRIEVE_MORE",
  "issues_found": [
    "Hypothesis doesn't answer the specific question about release EFFICIENCY",
    "No quantitative data provided (%, rate, etc.)"
  ],
  "missing_aspects": [
    "Drug release efficiency measurements",
    "Clinical or lab test results"
  ],
  "contradictions": [],
  "confidence_assessment": "LOW"
}}
```

Bad Response (avoid):
```json
{{
  "verdict": "PASS",
  "issues_found": [],
  "missing_aspects": [],
  "contradictions": [],
  "confidence_assessment": "HIGH"
}}
```
(Misses the fact that efficiency wasn't addressed)
""",
    temperature=0.05,
    max_tokens=1024,
)


# ============================================================
# CORTEX 2.0 PROMPTS
# ============================================================

CORTEX_DECOMPOSER = PromptTemplate(
    template="""Break this research query into {num_subtasks} focused sub-questions.
Each sub-question should cover a different aspect or angle of the original query.

USER QUERY: {query}

STEP 1 - IDENTIFY KEY ASPECTS:
What are the different aspects of this query that need to be researched?
- Aspect 1: ...
- Aspect 2: ...
- ...

STEP 2 - DESIGN SUB-TASKS:
Create {num_subtasks} sub-questions (one per aspect):
1. [Sub-question for aspect 1]
2. [Sub-question for aspect 2]
...

STEP 3 - VALIDATION:
Do these {num_subtasks} sub-questions FULLY cover the original query?
Are there any important aspects missing?

Return your analysis as JSON:
{{
  "aspects": ["aspect 1", "aspect 2", "aspect 3", ...],
  "sub_tasks": ["sub-question 1", "sub-question 2", ...],
  "coverage_check": "COMPLETE" or "PARTIAL - missing [describe what's missing]"
}}
""",
    examples="""EXAMPLE:
Query: "What are the main polymer-based drug delivery methods?"

Good Response:
```json
{{
  "aspects": [
    "Types of polymers used",
    "Delivery mechanisms",
    "Clinical applications",
    "Advantages and limitations",
    "Recent developments"
  ],
  "sub_tasks": [
    "What types of polymers are commonly used in drug delivery systems?",
    "What are the main mechanisms by which polymer-based systems deliver drugs?",
    "What clinical applications use polymer drug delivery?",
    "What are the key advantages and limitations of polymer-based delivery?",
    "What recent developments have occurred in polymer drug delivery?"
  ],
  "coverage_check": "COMPLETE"
}}
```

Bad Response (avoid):
```json
{{
  "aspects": ["polymers", "drugs"],
  "sub_tasks": [
    "What is polymer X?",
    "What is drug delivery?",
    "What are polymers?",
    "What are drugs?",
    "What is medicine?"
  ],
  "coverage_check": "COMPLETE"
}}
```
(Sub-tasks are too basic and don't address the query)
""",
    temperature=0.15,
    max_tokens=1024,
)


CORTEX_EXECUTOR = PromptTemplate(
    template="""Answer this sub-question with step-by-step reasoning.

SUB-QUESTION: {task}

EVIDENCE:
{evidence}

FORMAT YOUR RESPONSE:

<thinking>
Step 1: What does the evidence actually say about this question?
[Analyze systematically...]

Step 2: How confident can we be in this evidence?
[Assess quality and reliability...]

Step 3: What's the clearest answer we can provide?
[Synthesize...]
</thinking>

<answer>
[Your clear, evidence-based answer with specific citations]
</answer>

<confidence>HIGH/MEDIUM/LOW</confidence>
""",
    examples="""EXAMPLE:
Sub-question: "What types of polymers are commonly used in drug delivery?"
Evidence: [PLA, PLGA, chitosan mentioned in multiple sources...]

Good Response:
<thinking>
Step 1: Evidence mentions PLA, PLGA (synthetic), and chitosan (natural) across 3 sources
Step 2: Multiple independent sources = high confidence
Step 3: Can categorize into synthetic and natural polymers
</thinking>

<answer>
Common polymers in drug delivery include synthetic polymers like PLA (polylactic acid) and PLGA (poly(lactic-co-glycolic acid)), which are biodegradable [Smith2023.pdf, p.8], and natural polymers like chitosan, which offers biocompatibility [Jones2022.pdf, p.15].
</answer>

<confidence>HIGH</confidence>

Bad Response (avoid):
<thinking>
Polymers are used.
</thinking>

<answer>
Various polymers.
</answer>

<confidence>LOW</confidence>
(Not specific, no citations)
""",
    temperature=0.2,
    max_tokens=1024,
)


CORTEX_CROSS_CHECKER = PromptTemplate(
    template="""You are a consistency validator. Analyze these sub-task results for contradictions and gaps.

ORIGINAL QUERY: {query}

SUB-TASK RESULTS:
{results}

ANALYSIS:

1. CONTRADICTIONS: Do any answers conflict with each other?
   - Look for direct contradictions (A says X, B says not-X)
   - Look for inconsistent claims across sub-tasks

2. COVERAGE: Do these answers FULLY address the original query?
   - Are all aspects of the query covered?
   - What important information is missing?

3. CONFIDENCE: Which findings are well-supported vs. speculative?
   - Which sub-tasks have low confidence?
   - Do low-confidence tasks create uncertainty in the overall answer?

Return your analysis as JSON:
{{
  "contradictions": [
    {{"between": ["task 1", "task 3"], "issue": "description of contradiction", "severity": "HIGH or LOW"}}
  ],
  "coverage_gaps": ["gap 1", "gap 2"],
  "overall_verdict": "PASS" or "HAS_CONFLICTS"
}}

PASS = No major contradictions, coverage is acceptable
HAS_CONFLICTS = Significant contradictions or major coverage gaps detected
""",
    examples="""EXAMPLE:
Query: "What is the drug release efficiency of polymer X?"

Sub-task results:
Task 1: "Polymer X shows 85% release efficiency (Study A, 2023)"
Task 2: "Polymer X achieves 60% release (Study B, 2024)"
Task 3: "Polymer X is biocompatible"

Good Response:
```json
{{
  "contradictions": [
    {{
      "between": ["task 1", "task 2"],
      "issue": "Task 1 reports 85% efficiency (2023), but Task 2 reports 60% (2024)",
      "severity": "HIGH"
    }}
  ],
  "coverage_gaps": [
    "Experimental conditions not explained (may account for differences)"
  ],
  "overall_verdict": "HAS_CONFLICTS"
}}
```

Bad Response (avoid):
```json
{{
  "contradictions": [],
  "coverage_gaps": [],
  "overall_verdict": "PASS"
}}
```
(Missed the obvious 85% vs 60% contradiction)
""",
    temperature=0.05,
    max_tokens=1024,
)


CORTEX_RESOLVER = PromptTemplate(
    template="""You are a calm, objective conflict mediator.
    
Two or more research sub-tasks have produced conflicting information.
Your job is to resolve these contradictions if possible, or explain why they cannot be resolved.

CONFLICTS:
{conflicts}

EVIDENCE FROM SOURCES:
{evidence}

RESOLUTION STRATEGY:
1. Compare the sources: Are they peer-reviewed? Recent? Primary vs Secondary?
2. Check context: Do the sources talk about slightly different things (e.g., different conditions, species, etc.)?
3. Weigh the evidence: content quality, specific data points vs general statements.

Return your resolution as JSON:
{{
  "resolutions": [
    {{
      "conflict_id": 0,
      "resolution": "Explanation of which source is likely correct and why, or that both are correct in different contexts.",
      "confidence": "HIGH/MEDIUM/LOW"
    }}
  ]
}}
""",
    examples="""EXAMPLE:
Conflict: Task 1 says "Polymer X degrades in 2 weeks" vs Task 2 says "Polymer X is stable for months".
Evidence: Source A (2015) tested in acidic solution. Source B (2020) tested in neutral pH.

Resolution:
```json
{{
  "resolutions": [
    {{
      "conflict_id": 0,
      "resolution": "The contradiction is likely due to environmental conditions. Source A tested in acidic solution (fast degradation), while Source B tested in neutral pH (stable). Both are correct in their respective contexts.",
      "confidence": "HIGH"
    }}
  ]
}}
```
""",
    temperature=0.1,
    max_tokens=1024,
)


# ============================================================
# SYNTHESIZER PROMPTS (shared by both brains)
# ============================================================

SYNTHESIZER = PromptTemplate(
    template="""You are a research synthesis agent. Combine these findings into a comprehensive answer.

ORIGINAL QUERY: {query}

FINDINGS:
{findings}

{conflict_notice}

{gaps_notice}

Your task:
1. Synthesize the findings into a coherent answer
2. If contradictions exist, acknowledge them and explain which source is more reliable
3. If gaps exist, clearly state what information is missing
4. Provide an overall confidence assessment

COMPREHENSIVE SYNTHESIS:
""",
    temperature=0.2,
    max_tokens=1500,
)


# ============================================================
# VALIDATION UTILITIES
# ============================================================

def get_temperature_for_node(node_name: str) -> float:
    """Get recommended temperature for a specific node.

    Temperature optimization based on SOTA 2026 patterns.
    """
    temperatures = {
        "planner": 0.1,       # Consistent structure needed
        "decomposer": 0.15,   # Structured task breakdown
        "reasoner": 0.2,      # Balance creativity + factuality
        "executor": 0.2,      # Same as reasoner
        "critic": 0.05,       # Deterministic verification
        "cross_checker": 0.05,  # Strict contradiction detection
        "synthesizer": 0.2,   # Polished but grounded
    }
    return temperatures.get(node_name.lower(), 0.2)  # Default 0.2


def validate_xml_output(response: str, required_tags: list[str]) -> bool:
    """Validate that LLM response contains all required XML tags.

    Args:
        response: The LLM response text
        required_tags: List of tag names (without brackets) that must be present

    Returns:
        True if all required tags are present and properly closed
    """
    for tag in required_tags:
        opening = f"<{tag}>"
        closing = f"</{tag}>"
        if opening not in response or closing not in response:
            return False
        
        # Check that opening comes before closing
        open_idx = response.find(opening)
        close_idx = response.find(closing)
        if open_idx >= close_idx:
            return False
    
    return True


def validate_json_output(response: str, required_keys: list[str]) -> bool:
    """Validate that LLM response contains valid JSON with required keys.

    Args:
        response: The LLM response text
        required_keys: List of keys that must be present in the JSON

    Returns:
        True if response contains valid JSON with all required keys
    """
    import json
    import re
    
    # Try to extract JSON (handles markdown code blocks)
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Try to find raw JSON
        start = response.find("{")
        end = response.rfind("}") + 1
        if start < 0 or end <= start:
            return False
        json_str = response[start:end]
    
    try:
        data = json.loads(json_str)
        return all(key in data for key in required_keys)
    except (json.JSONDecodeError, ValueError):
        return False


def validate_reasoner_output(response: str) -> bool:
    """Validate Navigator/Cortex reasoner output format."""
    required_tags = ["thinking", "hypothesis", "confidence"]
    return validate_xml_output(response, required_tags)


def validate_executor_output(response: str) -> bool:
    """Validate Cortex executor output format."""
    required_tags = ["thinking", "answer", "confidence"]
    return validate_xml_output(response, required_tags)


def validate_planner_output(response: str) -> bool:
    """Validate Navigator planner output format."""
    required_keys = ["understanding", "information_needs", "search_terms", "potential_gaps"]
    return validate_json_output(response, required_keys)


def validate_decomposer_output(response: str) -> bool:
    """Validate Cortex decomposer output format."""
    required_keys = ["aspects", "sub_tasks", "coverage_check"]
    return validate_json_output(response, required_keys)


def validate_critic_output(response: str) -> bool:
    """Validate Navigator critic output format."""
    required_keys = ["verdict", "issues_found", "missing_aspects", "contradictions"]
    return validate_json_output(response, required_keys)


def validate_cross_checker_output(response: str) -> bool:
    """Validate Cortex cross-checker output format."""
    required_keys = ["contradictions", "coverage_gaps", "overall_verdict"]
    return validate_json_output(response, required_keys)


def validate_resolver_output(response: str) -> bool:
    """Validate Cortex resolver output format."""
    required_keys = ["resolutions"]
    return validate_json_output(response, required_keys)


# Map node names to their validation functions
VALIDATORS = {
    "planner": validate_planner_output,
    "decomposer": validate_decomposer_output,
    "reasoner": validate_reasoner_output,
    "executor": validate_executor_output,
    "critic": validate_critic_output,
    "cross_checker": validate_cross_checker_output,
    "resolver": validate_resolver_output,
}


def get_validator_for_node(node_name: str):
    """Get validation function for a specific node.

    Returns:
        Validation function or None if no validation needed
    """
    return VALIDATORS.get(node_name.lower())
