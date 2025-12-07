"""
OpenAI service using the new Responses API.
Handles communication with OpenAI API.
"""
from openai import OpenAI
from typing import List, Dict, Any, Optional, Tuple
import json
from config import get_settings
from core.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()

# Initialize OpenAI client
client = OpenAI(api_key=settings.openai_api_key)

# Model to use (as per assignment requirements)
CHAT_MODEL = "gpt-4.1-mini"

# Tool definition for semantic search (Milestone 4)
# Used for dynamic RAG mode switching with OpenAI tool calling
# Format matches official OpenAI documentation
SEMANTIC_SEARCH_TOOL = {
    "type": "function",
    "name": "semantic_search",
    "description": (
        "Search through uploaded PDF documents to find relevant information. "
        "ALWAYS use this tool when the user asks questions that require information "
        "from the uploaded documents. This includes questions about: "
        "document content, specific topics mentioned in files, facts, data, "
        "recommendations, or any details that would be in the PDFs. "
        "Examples: 'What does the document say about...?', 'Find information about...', "
        "'What is mentioned regarding...?', 'Summarize the section on...'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to find relevant chunks from the documents"
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top chunks to retrieve (default: 5, max: 20)",
                "default": 5,
                "minimum": 1,
                "maximum": 20
            }
        },
        "required": ["query"]
    }
}


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
        logger.debug(f"actual Message : {messages}")

        with open("context_msg.txt", "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(str(msg) + "\n")

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


def send_chat_completion_with_tools(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]]
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Send messages to OpenAI with tool calling support.

    Enables the LLM to decide whether to call a tool (e.g., semantic_search)
    or respond directly. Used for dynamic RAG mode switching.

    Args:
        messages: List of OpenAI-style message dictionaries
        tools: List of tool definitions (e.g., [SEMANTIC_SEARCH_TOOL])

    Returns:
        Tuple of (response_text, tool_call_dict):
        - If LLM responds directly: (response_text, None)
        - If LLM calls a tool: (None, {"name": "...", "arguments": {...}})

    Raises:
        Exception: If OpenAI API call fails

    Example:
        >>> # LLM decides to respond directly
        >>> response, tool_call = send_chat_completion_with_tools(
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     tools=[SEMANTIC_SEARCH_TOOL]
        ... )
        >>> # response = "Hi there!", tool_call = None

        >>> # LLM decides to call tool
        >>> response, tool_call = send_chat_completion_with_tools(
        ...     messages=[{"role": "user", "content": "What is the main topic?"}],
        ...     tools=[SEMANTIC_SEARCH_TOOL]
        ... )
        >>> # response = None, tool_call = {"name": "semantic_search", "arguments": {...}}
    """
    try:
        logger.info(
            f"Sending chat request with {len(tools)} tool(s) "
            f"(model: {CHAT_MODEL})"
        )
        logger.info(f"Message count: {len(messages)}")
        logger.info(f"Tools: {[t['name'] for t in tools]}")
        logger.info(f"Messages being sent: {messages}")

        # Call OpenAI with tools enabled
        response = client.responses.create(
            model=CHAT_MODEL,
            input=messages,
            tools=tools
        )

        # Check if LLM called a tool using Responses API format
        # In Responses API, tool calls are in response.output (not response.tool_calls)
        if hasattr(response, 'output') and response.output:
            # Check if output contains a function tool call
            for output_item in response.output:
                if hasattr(output_item, 'type') and output_item.type == 'function_call':
                    # LLM called a tool!
                    tool_name = output_item.name
                    tool_arguments = json.loads(output_item.arguments) if isinstance(output_item.arguments, str) else output_item.arguments

                    logger.info(
                        f"LLM called tool: {tool_name} with arguments: {tool_arguments}"
                    )

                    return None, {
                        "name": tool_name,
                        "arguments": tool_arguments
                    }

        # LLM responded directly (no tool call)
        # output_text should contain the response when no tool is called
        assistant_message = response.output_text if hasattr(response, 'output_text') else ""

        logger.info(
            f"LLM responded directly (no tool call), "
            f"response length: {len(assistant_message)} characters"
        )

        return assistant_message, None

    except Exception as e:
        logger.error(f"OpenAI API error with tools: {str(e)}")
        raise
