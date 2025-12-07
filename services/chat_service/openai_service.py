"""
OpenAI service using the new Responses API.
Handles communication with OpenAI API.
"""
from openai import OpenAI
from typing import List, Dict, Any
from config import get_settings
from core.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()

# Initialize OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Model to use (as per assignment requirements)
CHAT_MODEL = "gpt-4.1-mini"


def send_chat_completion(messages: List[Dict[str, Any]]) -> str:
    """
    Send messages to OpenAI using the new Responses API and return assistant response.

    Args:
        messages: List of OpenAI-style message dictionaries.
                  Example:
                  [
                      {"role": "user", "content": "Hello"},
                      {"role": "assistant", "content": "Hi there!"}
                  ]

    Returns:
        The assistant's response text.

    Raises:
        Exception: If OpenAI API call fails.
    """

    # Convert messages (ChatCompletion format) to Responses API "input"
    # The Responses API accepts the same structure for multi-turn chat.
    try:
        logger.info(f"Sending chat request using Responses API (model: {CHAT_MODEL})")
        logger.debug(f"Message count: {len(messages)}")

        # with open("context_msg.txt", "w", encoding="utf-8") as f:
        #     for msg in messages:
        #         f.write(str(msg) + "\n")

        response = client.responses.create(
            model=CHAT_MODEL,
            input=messages   # direct pass-through supported
        )

        # New unified assistant output
        assistant_message = response.output_text

        logger.info("Successfully received response from OpenAI")
        logger.debug(f"Response length: {len(assistant_message)} characters")

        return assistant_message

    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise
