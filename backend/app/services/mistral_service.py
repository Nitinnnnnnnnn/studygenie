import os
import json
import logging
from typing import List, Dict, Any, Optional
import requests
from app.config import settings

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1"


class MistralService:
    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != "your_mistral_api_key_here")

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for a list of text strings using mistral-embed."""
        if not self.is_configured():
            logger.warning("MISTRAL_API_KEY not configured. Generating dummy embeddings for local dev.")
            # Deterministic fallback embedding for testing without API key
            return [[float(hash(t + str(i)) % 1000) / 1000.0 for i in range(1024)] for t in texts]

        try:
            # Batch if large
            embeddings = []
            batch_size = 32
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = requests.post(
                    f"{MISTRAL_API_URL}/embeddings",
                    headers=self.headers,
                    json={
                        "model": settings.EMBEDDING_MODEL,
                        "input": batch
                    },
                    timeout=60
                )
                response.raise_for_status()
                data = response.json()
                embeddings.extend([item["embedding"] for item in data["data"]])
            return embeddings
        except Exception as e:
            logger.error(f"Error calling Mistral Embeddings API: {e}")
            raise RuntimeError(f"Mistral Embeddings API error: {str(e)}")

    def generate_rag_response(
        self,
        context_passages: List[Dict[str, Any]],
        question: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Generate a grounded answer using retrieved context passages with exact citations."""
        if not self.is_configured():
            mock_sources = "\n".join([f"- [{p['filename']}, Page {p['page']}]" for p in context_passages[:2]])
            return (
                f"**[Demo Mode - Set MISTRAL_API_KEY in .env for live AI]**\n\n"
                f"Based on your notes, here is the synthesized answer for: *'{question}'*.\n\n"
                f"**Relevant key concepts found:**\n"
                f"The uploaded document covers core definitions and methodologies matching your query.\n\n"
                f"**Sources Referenced:**\n{mock_sources}"
            )

        # Build context string with explicit document names and page numbers
        formatted_context = ""
        for idx, p in enumerate(context_passages, 1):
            formatted_context += (
                f"\n--- SOURCE [{idx}]: File: {p['filename']}, Page: {p['page']} ---\n"
                f"{p['chunk_text']}\n"
            )

        system_prompt = (
            "You are StudyGenie, an expert AI academic tutor and study assistant. "
            "Your task is to answer the student's question accurately and thoroughly, strictly using the provided context passages from their uploaded study notes.\n\n"
            "GUIDELINES:\n"
            "1. Base your answer ONLY on the provided context passages. Do NOT make up facts or extrapolate beyond what is documented.\n"
            "2. When stating facts or quoting concepts, ALWAYS cite the source using the exact format: [Doc: <filename>, Page <page_number>].\n"
            "3. Format your response cleanly using Markdown headings, bullet points, and bold text for key terms to make it easy for students to study.\n"
            "4. If the provided context does not contain enough information to fully answer the question, clearly state what is covered and mention what is missing."
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Append recent history if present (up to 4 previous turns)
        if chat_history:
            for turn in chat_history[-4:]:
                messages.append({"role": turn["sender"], "content": turn["content"]})

        user_content = (
            f"STUDY NOTES CONTEXT:\n{formatted_context}\n\n"
            f"STUDENT QUESTION:\n{question}\n\n"
            "Please provide a well-structured, clear explanation with inline citations [Doc: <filename>, Page <page_number>]."
        )
        messages.append({"role": "user", "content": user_content})

        try:
            response = requests.post(
                f"{MISTRAL_API_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": settings.CHAT_MODEL,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 1200
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            raise RuntimeError(f"Mistral Chat API error: {str(e)}")

    def generate_quiz_questions(
        self,
        context_text: str,
        difficulty: str,
        total_questions: int,
        topic: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate structured multiple choice questions from document context."""
        if not self.is_configured():
            # Provide sample quiz questions for instant testing
            return [
                {
                    "question_text": f"Sample {difficulty} question #{i+1} from your uploaded study notes?",
                    "options": [
                        "First core principle option A",
                        "Second principle option B (Correct)",
                        "Third principle option C",
                        "Fourth principle option D"
                    ],
                    "correct_option_index": 1,
                    "explanation": f"Option B is the correct answer according to the study material for question {i+1}."
                }
                for i in range(total_questions)
            ]

        topic_instruction = f" Focus specifically on the topic '{topic}'." if topic else ""

        system_prompt = (
            "You are a strict educational exam creator. You generate rigorous Multiple Choice Questions (MCQs) "
            "based strictly on the provided study notes. You MUST output ONLY valid, raw JSON (an array of objects) "
            "with no markdown code fences, no extra text, and no preamble."
        )

        user_prompt = f"""
Given the following study text, generate exactly {total_questions} {difficulty} difficulty multiple-choice questions (MCQs).{topic_instruction}

DIFFICULTY GUIDELINES:
- Easy: Direct recall of definitions, key terms, and core facts stated in the text.
- Medium: Conceptual understanding, distinguishing between two related ideas, applying concepts.
- Hard: Deep analytical reasoning, multi-step scenario problems, edge cases from the text.

CRITICAL RULES:
1. Each question must have EXACTLY 4 plausible options.
2. Only ONE option must be correct.
3. Provide a clear, educational explanation (2-3 sentences) explaining why the correct option is right and referencing the context.
4. Return ONLY a JSON array matching this exact schema:

[
  {{
    "question_text": "string (the question)",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_option_index": 0,  // Integer 0, 1, 2, or 3 pointing to the correct item in options
    "explanation": "string (detailed explanation of the correct answer)"
  }}
]

STUDY MATERIAL:
{context_text[:12000]}
"""

        try:
            response = requests.post(
                f"{MISTRAL_API_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": settings.CHAT_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 3000,
                    "response_format": {"type": "json_object"}
                },
                timeout=90
            )
            response.raise_for_status()
            data = response.json()
            raw_content = data["choices"][0]["message"]["content"].strip()

            # Clean potential markdown wrappers
            if raw_content.startswith("```json"):
                raw_content = raw_content[7:]
            if raw_content.startswith("```"):
                raw_content = raw_content[3:]
            if raw_content.endswith("```"):
                raw_content = raw_content[:-3]
            raw_content = raw_content.strip()

            parsed = json.loads(raw_content)
            # If wrapped in a dictionary key like {"questions": [...]}
            if isinstance(parsed, dict):
                for key in ["questions", "quiz", "data", "items"]:
                    if key in parsed and isinstance(parsed[key], list):
                        parsed = parsed[key]
                        break
                if isinstance(parsed, dict):
                    parsed = list(parsed.values())[0]

            if not isinstance(parsed, list):
                raise ValueError("Parsed JSON is not an array of questions")

            # Validate each question structure
            valid_questions = []
            for item in parsed[:total_questions]:
                if (
                    "question_text" in item
                    and "options" in item
                    and len(item["options"]) == 4
                    and "correct_option_index" in item
                    and 0 <= int(item["correct_option_index"]) <= 3
                    and "explanation" in item
                ):
                    valid_questions.append({
                        "question_text": str(item["question_text"]),
                        "options": [str(opt) for opt in item["options"]],
                        "correct_option_index": int(item["correct_option_index"]),
                        "explanation": str(item["explanation"])
                    })

            if not valid_questions:
                raise ValueError("No valid questions parsed from LLM response")

            return valid_questions

        except Exception as e:
            logger.error(f"Error generating quiz from Mistral: {e}")
            raise RuntimeError(f"Failed to generate quiz: {str(e)}")


mistral_service = MistralService()
