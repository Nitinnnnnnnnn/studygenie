import json
import logging
from typing import List, Dict, Any, Optional

from groq import Groq

from app.config import settings


logger = logging.getLogger(__name__)


class MistralService:
    """
    StudyGenie AI service.

    Despite the class name MistralService, this service no longer uses
    Mistral. The name is kept so that the rest of the existing StudyGenie
    code does not need to be changed.

   AI architecture:
    - Embeddings: ChromaDB built-in embedding function
    - Chat/RAG: Groq
    - Quiz generation: Groq
    """

    def __init__(self):
        # ==============================
        # Groq configuration
        # ==============================

        self.api_key = settings.GROQ_API_KEY

        self.client = None

        if self.api_key:
            self.client = Groq(api_key=self.api_key)

       

    

    # ============================================================
    # Configuration
    # ============================================================

    def is_configured(self) -> bool:
        """Check whether Groq API is configured."""

        return bool(
            self.api_key
            and self.api_key != "your_groq_api_key_here"
            and self.client is not None
        )


    # ============================================================
    # RAG CHAT
    # ============================================================

    def generate_rag_response(
        self,
        context_passages: List[Dict[str, Any]],
        question: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate a grounded answer using retrieved document passages.

        Groq is used for text generation.
        """

        # --------------------------------------------------------
        # Demo mode if Groq is not configured
        # --------------------------------------------------------

        if not self.is_configured():

            mock_sources = "\n".join(
                [
                    f"- [{p['filename']}, Page {p['page']}]"
                    for p in context_passages[:2]
                ]
            )

            return (
                "**[Demo Mode - Set GROQ_API_KEY in .env for live AI]**\n\n"
                f"Based on your notes, here is the synthesized answer "
                f"for: *'{question}'*.\n\n"
                "**Relevant key concepts found:**\n"
                "The uploaded document contains information relevant "
                "to your question.\n\n"
                f"**Sources Referenced:**\n{mock_sources}"
            )

        # --------------------------------------------------------
        # Build document context
        # --------------------------------------------------------

        formatted_context = ""

        for idx, passage in enumerate(context_passages, 1):

            formatted_context += (
                f"\n--- SOURCE [{idx}]: "
                f"File: {passage['filename']}, "
                f"Page: {passage['page']} ---\n"
                f"{passage['chunk_text']}\n"
            )

        # --------------------------------------------------------
        # System prompt
        # --------------------------------------------------------

        system_prompt = (
            "You are StudyGenie, an expert AI academic tutor and "
            "study assistant. "

            "Your task is to answer the student's question accurately "
            "and thoroughly, strictly using the provided context "
            "passages from their uploaded study notes.\n\n"

            "GUIDELINES:\n"

            "1. Base your answer ONLY on the provided context passages. "
            "Do NOT make up facts or extrapolate beyond what is documented.\n"

            "2. When stating facts or quoting concepts, ALWAYS cite "
            "the source using the exact format: "
            "[Doc: <filename>, Page <page_number>].\n"

            "3. Format your response cleanly using Markdown headings, "
            "bullet points, and bold text for key terms to make it "
            "easy for students to study.\n"

            "4. If the provided context does not contain enough "
            "information to fully answer the question, clearly state "
            "what is covered and mention what is missing."
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        # --------------------------------------------------------
        # Add previous conversation history
        # --------------------------------------------------------

        if chat_history:

            for turn in chat_history[-4:]:

                messages.append(
                    {
                        "role": turn["sender"],
                        "content": turn["content"]
                    }
                )

        # --------------------------------------------------------
        # User message
        # --------------------------------------------------------

        user_content = (
            f"STUDY NOTES CONTEXT:\n"
            f"{formatted_context}\n\n"

            f"STUDENT QUESTION:\n"
            f"{question}\n\n"

            "Please provide a well-structured, clear explanation "
            "with inline citations "
            "[Doc: <filename>, Page <page_number>]."
        )

        messages.append(
            {
                "role": "user",
                "content": user_content
            }
        )

        # --------------------------------------------------------
        # Call Groq
        # --------------------------------------------------------

        try:

            response = self.client.chat.completions.create(
                model=settings.GROQ_CHAT_MODEL,
                messages=messages,
                temperature=0.2,
                max_tokens=1200
            )

            return response.choices[0].message.content

        except Exception as e:

            logger.error(
                f"Error generating RAG response with Groq: {e}"
            )

            raise RuntimeError(
                f"Groq Chat API error: {str(e)}"
            )

    # ============================================================
    # QUIZ GENERATION
    # ============================================================

    def generate_quiz_questions(
        self,
        context_text: str,
        difficulty: str,
        total_questions: int,
        topic: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate structured multiple-choice questions using Groq.
        """

        # --------------------------------------------------------
        # Demo mode
        # --------------------------------------------------------

        if not self.is_configured():

            return [
                {
                    "question_text": (
                        f"Sample {difficulty} question #{i + 1} "
                        "from your uploaded study notes?"
                    ),

                    "options": [
                        "First core principle option A",
                        "Second principle option B (Correct)",
                        "Third principle option C",
                        "Fourth principle option D"
                    ],

                    "correct_option_index": 1,

                    "explanation": (
                        f"Option B is the correct answer according "
                        f"to the study material for question {i + 1}."
                    )
                }

                for i in range(total_questions)
            ]

        # --------------------------------------------------------
        # Topic instruction
        # --------------------------------------------------------

        topic_instruction = (
            f" Focus specifically on the topic '{topic}'."
            if topic
            else ""
        )

        # --------------------------------------------------------
        # System prompt
        # --------------------------------------------------------

        system_prompt = (
            "You are a strict educational exam creator. "
            "You generate rigorous Multiple Choice Questions (MCQs) "
            "based strictly on the provided study notes.\n\n"

            "Return a JSON object with a single key named "
            "\"questions\". The value of \"questions\" must be an "
            "array of question objects.\n\n"

            "Do not include markdown code fences. "
            "Do not include explanations outside the JSON object."
        )

        # --------------------------------------------------------
        # User prompt
        # --------------------------------------------------------

        user_prompt = f"""
Given the following study text, generate exactly
{total_questions} {difficulty} difficulty multiple-choice
questions (MCQs).{topic_instruction}

DIFFICULTY GUIDELINES:

- Easy: Direct recall of definitions, key terms, and core facts
  stated in the text.

- Medium: Conceptual understanding, distinguishing between two
  related ideas, applying concepts.

- Hard: Deep analytical reasoning, multi-step scenario problems,
  edge cases from the text.

CRITICAL RULES:

1. Each question must have EXACTLY 4 plausible options.

2. Only ONE option must be correct.

3. correct_option_index must be an integer:
   0, 1, 2, or 3.

4. Provide a clear educational explanation of 2-3 sentences
   explaining why the correct option is right.

5. Questions must be based ONLY on the provided study material.

6. Return exactly {total_questions} questions.

JSON FORMAT:

{{
    "questions": [
        {{
            "question_text": "string",
            "options": [
                "Option A",
                "Option B",
                "Option C",
                "Option D"
            ],
            "correct_option_index": 0,
            "explanation": "string"
        }}
    ]
}}

STUDY MATERIAL:

{context_text[:12000]}
"""

        # --------------------------------------------------------
        # Call Groq
        # --------------------------------------------------------

        try:

            response = self.client.chat.completions.create(
                model=settings.GROQ_CHAT_MODEL,

                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],

                temperature=0.3,
                max_tokens=3000,

                response_format={
                    "type": "json_object"
                }
            )

            raw_content = (
                response.choices[0]
                .message
                .content
                .strip()
            )

            # ----------------------------------------------------
            # Clean markdown wrappers if model returns them
            # ----------------------------------------------------

            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]

            if raw_content.startswith("```"):
                raw_content = raw_content[3:]

            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]

            raw_content = raw_content.strip()

            # ----------------------------------------------------
            # Parse JSON
            # ----------------------------------------------------

            parsed = json.loads(raw_content)

            # Expected:
            # {
            #     "questions": [...]
            # }

            if isinstance(parsed, dict):

                if (
                    "questions" in parsed
                    and isinstance(parsed["questions"], list)
                ):
                    parsed = parsed["questions"]

                else:

                    # Backward-compatible handling
                    for key in [
                        "quiz",
                        "data",
                        "items"
                    ]:

                        if (
                            key in parsed
                            and isinstance(parsed[key], list)
                        ):
                            parsed = parsed[key]
                            break

            # ----------------------------------------------------
            # Validate array
            # ----------------------------------------------------

            if not isinstance(parsed, list):

                raise ValueError(
                    "Parsed JSON is not an array of questions"
                )

            # ----------------------------------------------------
            # Validate every question
            # ----------------------------------------------------

            valid_questions = []

            for item in parsed[:total_questions]:

                if not isinstance(item, dict):
                    continue

                if (
                    "question_text" in item
                    and "options" in item
                    and isinstance(item["options"], list)
                    and len(item["options"]) == 4
                    and "correct_option_index" in item
                    and "explanation" in item
                ):

                    try:

                        correct_index = int(
                            item["correct_option_index"]
                        )

                    except (ValueError, TypeError):

                        continue

                    if not 0 <= correct_index <= 3:
                        continue

                    valid_questions.append(
                        {
                            "question_text": str(
                                item["question_text"]
                            ),

                            "options": [
                                str(option)
                                for option in item["options"]
                            ],

                            "correct_option_index": correct_index,

                            "explanation": str(
                                item["explanation"]
                            )
                        }
                    )

            # ----------------------------------------------------
            # Make sure we actually received questions
            # ----------------------------------------------------

            if not valid_questions:

                raise ValueError(
                    "No valid questions parsed from Groq response"
                )

            return valid_questions

        except Exception as e:

            logger.error(
                f"Error generating quiz with Groq: {e}"
            )

            raise RuntimeError(
                f"Failed to generate quiz: {str(e)}"
            )


# ================================================================
# Keep the existing variable name so other StudyGenie files
# don't need to be changed.
# ================================================================

mistral_service = MistralService()