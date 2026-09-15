"""
Teacher Digital Assistant — Lesson Plan AI Service

This module connects the Teacher workspace to the configured AI provider.

Current provider:
    OpenRouter

Current development model:
    openrouter/free

The service returns structured Python data.
It does not render HTML and does not write directly to the database.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import (
    MASTER_TEACHER_PROMPT,
    build_lesson_plan_prompt,
)


load_dotenv()


class LessonPlanAIError(Exception):
    """Base exception for lesson-plan AI errors."""


class LessonPlanAIConfigurationError(LessonPlanAIError):
    """Raised when AI configuration is missing or invalid."""


class LessonPlanAIResponseError(LessonPlanAIError):
    """Raised when the AI response cannot be parsed or validated."""


REQUIRED_TOP_LEVEL_KEYS = {
    "lesson_objectives",
    "prior_ideas",
    "exploration",
    "discussion",
    "application",
    "evaluation",
    "references",
    "home_task",
}


REQUIRED_STAGE_KEYS = {
    "mode",
    "teacher_activities",
    "student_activities",
}


def get_openrouter_client():
    """
    Create and return an OpenRouter-compatible OpenAI client.

    Configuration is read from environment variables so that API credentials
    never need to be stored in application source code.
    """

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise LessonPlanAIConfigurationError(
            "OPENROUTER_API_KEY is not configured."
        )

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def get_model_name():
    """
    Return the configured OpenRouter model.

    The free router is the default for the current development phase.
    """

    return os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/free",
    )


def validate_lesson_plan_response(data):
    """
    Validate the structure returned by the AI.

    This function deliberately validates structure rather than attempting
    to judge the educational quality of the generated lesson.
    """

    if not isinstance(data, dict):
        raise LessonPlanAIResponseError(
            "AI response must be a JSON object."
        )

    missing_keys = REQUIRED_TOP_LEVEL_KEYS - set(data.keys())

    if missing_keys:
        raise LessonPlanAIResponseError(
            "AI response is missing required fields: "
            + ", ".join(sorted(missing_keys))
        )

    if not isinstance(data["lesson_objectives"], list):
        raise LessonPlanAIResponseError(
            "lesson_objectives must be a list."
        )

    if not isinstance(data["references"], list):
        raise LessonPlanAIResponseError(
            "references must be a list."
        )

    if not isinstance(data["home_task"], str):
        raise LessonPlanAIResponseError(
            "home_task must be a string."
        )

    stage_names = [
        "prior_ideas",
        "exploration",
        "discussion",
        "application",
        "evaluation",
    ]

    for stage_name in stage_names:
        stage = data[stage_name]

        if not isinstance(stage, dict):
            raise LessonPlanAIResponseError(
                f"{stage_name} must be an object."
            )

        missing_stage_keys = REQUIRED_STAGE_KEYS - set(stage.keys())

        if missing_stage_keys:
            raise LessonPlanAIResponseError(
                f"{stage_name} is missing required fields: "
                + ", ".join(sorted(missing_stage_keys))
            )

        for field_name in REQUIRED_STAGE_KEYS:
            if not isinstance(stage[field_name], str):
                raise LessonPlanAIResponseError(
                    f"{stage_name}.{field_name} must be a string."
                )

    return data


def extract_response_content(response):
    """
    Extract text content from an OpenAI-compatible chat completion response.
    """

    if not response or not response.choices:
        raise LessonPlanAIResponseError(
            "The AI provider returned an empty response."
        )

    message = response.choices[0].message

    if not message or not message.content:
        raise LessonPlanAIResponseError(
            "The AI provider returned an empty message."
        )

    return message.content.strip()


def parse_json_response(content):
    """
    Parse the AI response as JSON.

    The master prompt requests JSON-only output. We first attempt strict
    parsing. A small fallback handles accidental Markdown code fences
    without changing the actual lesson content.
    """

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    cleaned = content.strip()

    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()

        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()

            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LessonPlanAIResponseError(
            "The AI provider did not return valid JSON."
        ) from exc


def generate_lesson_plan(lesson_data):
    """
    Generate structured lesson-plan content.

    Parameters
    ----------
    lesson_data:
        Dictionary containing the teacher's lesson information.

    Returns
    -------
    dict
        Validated structured lesson-plan data.

    Raises
    ------
    LessonPlanAIError
        If configuration, API communication, parsing, or validation fails.
    """

    client = get_openrouter_client()
    model = get_model_name()

    user_prompt = build_lesson_plan_prompt(
        lesson_data
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": MASTER_TEACHER_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.2,
        )
    except Exception as exc:
        raise LessonPlanAIError(
            f"Unable to contact the AI provider: {exc}"
        ) from exc

    content = extract_response_content(response)
    data = parse_json_response(content)

    return validate_lesson_plan_response(data)