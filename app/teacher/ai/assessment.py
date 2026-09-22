"""
AI Assessment Question Generator

Generates structured assessment questions using the configured
OpenRouter model.

This module only generates and validates AI content.
It does not save questions to the database.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class AssessmentAIError(Exception):
    """Raised when AI assessment generation fails."""


EXPECTED_QUESTION_KEYS = {
    "question_type",
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_answer",
    "marks",
    "explanation",
}


def _get_client():
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise AssessmentAIError(
            "OPENROUTER_API_KEY is not configured."
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def _get_model():
    model = os.getenv(
        "OPENROUTER_MODEL",
        "openrouter/free",
    )

    if not model:
        raise AssessmentAIError(
            "OPENROUTER_MODEL is not configured."
        )

    return model


def _parse_json_response(content):
    """
    Parse JSON returned by the AI.

    Handles both plain JSON and JSON wrapped in
    a markdown code fence.
    """

    if not content:
        raise AssessmentAIError(
            "The AI returned an empty response."
        )

    content = content.strip()

    if content.startswith("```"):
        lines = content.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    try:
        return json.loads(content)

    except json.JSONDecodeError as exc:
        raise AssessmentAIError(
            "The AI returned invalid JSON."
        ) from exc


def _validate_questions(data):
    """
    Validate the structure returned by the AI.
    """

    if not isinstance(data, dict):
        raise AssessmentAIError(
            "The AI response must be a JSON object."
        )

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise AssessmentAIError(
            "The AI response must contain a 'questions' list."
        )

    validated_questions = []

    for index, question in enumerate(questions, start=1):

        if not isinstance(question, dict):
            raise AssessmentAIError(
                f"Question {index} is not a valid object."
            )

        missing_keys = (
            EXPECTED_QUESTION_KEYS
            - set(question.keys())
        )

        if missing_keys:
            raise AssessmentAIError(
                f"Question {index} is missing required fields: "
                f"{', '.join(sorted(missing_keys))}."
            )

        question_type = str(
            question.get("question_type") or ""
        ).strip().lower()

        if question_type not in {
            "mcq",
            "short_answer",
            "theory",
        }:
            raise AssessmentAIError(
                f"Question {index} has an invalid question type."
            )

        question_text = str(
            question.get("question_text") or ""
        ).strip()

        if not question_text:
            raise AssessmentAIError(
                f"Question {index} has no question text."
            )

        try:
            marks = int(question.get("marks", 1))
        except (TypeError, ValueError) as exc:
            raise AssessmentAIError(
                f"Question {index} has invalid marks."
            ) from exc

        if marks < 1:
            raise AssessmentAIError(
                f"Question {index} must have at least 1 mark."
            )

        validated_questions.append(
            {
                "question_type": question_type,
                "question_text": question_text,
                "option_a": str(
                    question.get("option_a") or ""
                ).strip(),
                "option_b": str(
                    question.get("option_b") or ""
                ).strip(),
                "option_c": str(
                    question.get("option_c") or ""
                ).strip(),
                "option_d": str(
                    question.get("option_d") or ""
                ).strip(),
                "correct_answer": str(
                    question.get("correct_answer") or ""
                ).strip(),
                "marks": marks,
                "explanation": str(
                    question.get("explanation") or ""
                ).strip(),
            }
        )

    return validated_questions


def _build_system_prompt():
    return """
You are a Nigerian secondary-school assessment question generator.

Generate high-quality questions appropriate for the supplied
subject, class, topic and assessment parameters.

The supplied topic is authoritative for this assessment.

Follow these rules:

1. Stay strictly within the supplied topic.
2. Respect the supplied class level.
3. Use clear Nigerian secondary-school English.
4. Questions must test understanding, not merely random recall,
   unless the requested parameters specifically require recall.
5. Do not invent syllabus claims, examination requirements,
   textbook references or facts.
6. For MCQ questions:
   - Provide exactly four options.
   - Only one option must be correct.
   - The correct answer must be A, B, C or D.
   - Distractors must be plausible but clearly incorrect.
7. For short-answer and theory questions:
   - Options may be empty.
   - Provide an appropriate expected answer or marking guidance
     in correct_answer.
8. Every question must have a positive integer mark value.
9. Provide a concise explanation or marking guidance where useful.
10. Do not include question numbers in question_text.
11. Return JSON only.
12. Do not wrap the JSON in markdown.

Required response structure:

{
  "questions": [
    {
      "question_type": "mcq",
      "question_text": "",
      "option_a": "",
      "option_b": "",
      "option_c": "",
      "option_d": "",
      "correct_answer": "",
      "marks": 1,
      "explanation": ""
    }
  ]
}
""".strip()


def _build_user_prompt(
    subject,
    class_name,
    topic,
    number_of_questions,
    question_type,
    difficulty,
    examination_relevance=None,
    additional_instructions=None,
):
    prompt = f"""
Generate exactly {number_of_questions} assessment questions.

Assessment details:

Subject:
{subject}

Class:
{class_name}

Topic:
{topic}

Question Type:
{question_type}

Difficulty:
{difficulty}
""".strip()

    if examination_relevance:
        prompt += f"""

Examination / Curriculum Context:
{examination_relevance}
"""

    if additional_instructions:
        prompt += f"""

Additional Teacher Instructions:
{additional_instructions}
"""

    prompt += """

Return exactly the requested number of questions.
Return JSON only.
"""

    return prompt.strip()


def generate_assessment_questions(
    subject,
    class_name,
    topic,
    number_of_questions,
    question_type="mcq",
    difficulty="mixed",
    examination_relevance=None,
    additional_instructions=None,
):
    """
    Generate assessment questions using the configured AI model.

    Returns:
        list[dict]: Validated question dictionaries.
    """

    try:
        number_of_questions = int(
            number_of_questions
        )
    except (TypeError, ValueError) as exc:
        raise AssessmentAIError(
            "Number of questions must be a valid integer."
        ) from exc

    if number_of_questions < 1:
        raise AssessmentAIError(
            "Number of questions must be at least 1."
        )

    if number_of_questions > 100:
        raise AssessmentAIError(
            "You can generate a maximum of 100 questions at once."
        )

    if not subject or not class_name or not topic:
        raise AssessmentAIError(
            "Subject, class and topic are required."
        )

    client = _get_client()
    model = _get_model()

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": _build_system_prompt(),
            },
            {
                "role": "user",
                "content": _build_user_prompt(
                    subject=subject,
                    class_name=class_name,
                    topic=topic,
                    number_of_questions=number_of_questions,
                    question_type=question_type,
                    difficulty=difficulty,
                    examination_relevance=(
                        examination_relevance
                    ),
                    additional_instructions=(
                        additional_instructions
                    ),
                ),
            },
        ],
    )

    try:
        content = response.choices[0].message.content

    except (AttributeError, IndexError) as exc:
        raise AssessmentAIError(
            "The AI response did not contain usable content."
        ) from exc

    data = _parse_json_response(content)

    questions = _validate_questions(data)

    if len(questions) != number_of_questions:
        raise AssessmentAIError(
            "The AI returned "
            f"{len(questions)} questions instead of "
            f"{number_of_questions}."
        )

    return questions