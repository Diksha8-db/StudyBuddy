"""
AWS Bedrock Evaluator for VivaMate (AWS Builder Challenge).

When BEDROCK_MODEL_ID is set in the environment, this module evaluates student
viva responses using the AWS Bedrock Converse API with an academic rubric.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("studybuddy.evaluator")


def is_bedrock_enabled() -> bool:
    """Check if AWS Bedrock evaluation is configured."""
    return bool(os.environ.get("BEDROCK_MODEL_ID"))


def evaluate_viva_answer_bedrock(
    question: str,
    answer: str,
    topic: str,
    difficulty: str = "intermediate",
) -> Optional[Dict[str, Any]]:
    """
    Evaluate a student's viva response using AWS Bedrock Converse API.

    Args:
        question: The viva question that was asked.
        answer: The student's response.
        topic: The subject/topic of the viva.
        difficulty: The difficulty level (beginner, intermediate, advanced).

    Returns:
        Dict with score (0-10), feedback, and missed_points, or None if Bedrock is not configured.
    """
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id:
        return None

    try:
        import boto3
    except ImportError:
        logger.warning("boto3 is not installed; cannot evaluate via AWS Bedrock.")
        return None

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    prompt = f"""You are an expert academic viva examiner assessing a student's spoken response.
Topic: {topic}
Difficulty level: {difficulty}
Question: {question}
Student's spoken answer: {answer}

Evaluate the student's answer fairly on a 0 to 10 scale:
- 9-10: Complete, highly accurate, demonstrates deep conceptual mastery.
- 7-8: Mostly accurate, but missed minor nuances.
- 4-6: Partial recall with conceptual gaps or missing core elements.
- 0-3: Substantially incorrect, irrelevant, or severely incomplete.

Return ONLY a valid JSON object matching this exact schema:
{{
  "score": <integer from 0 to 10>,
  "feedback": "<1-2 sentences of encouraging, voice-friendly spoken feedback without markdown>",
  "missed_points": ["<key concept or element missed>", ...]
}}"""

    try:
        client = boto3.client("bedrock-runtime", region_name=region)
        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ]

        response = client.converse(
            modelId=model_id,
            messages=messages,
            inferenceConfig={
                "temperature": 0.2,
                "maxTokens": 300,
            },
        )

        output_text = response["output"]["message"]["content"][0]["text"]

        # Parse JSON from model output
        json_match = re.search(r"\{.*\}", output_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            score = max(0, min(10, int(data.get("score", 5))))
            feedback = str(data.get("feedback", "Good effort.")).strip()
            missed = data.get("missed_points", [])
            if not isinstance(missed, list):
                missed = [str(missed)]
            return {
                "score": score,
                "feedback": feedback,
                "missed_points": [str(m) for m in missed],
            }
    except Exception as e:
        logger.error(f"Error calling AWS Bedrock Converse API: {e}")
        return None

    return None
