"""
Message builder utility for constructing OpenAI messages.
Handles message patching with PDF files for the Responses API.
"""
from typing import Dict, Any, List, Optional
from core.utils.logger import setup_logger

logger = setup_logger(__name__)


def build_user_message(text: str, pdf_base64: Optional[str] = None, filename: str = "document.pdf") -> Dict[str, Any]:
    """
    Build a user message with optional PDF attachment.

    Args:
        text: User's text message
        pdf_base64: Optional base64-encoded PDF string
        filename: PDF filename (default: "document.pdf")

    Returns:
        Message dictionary in Responses API format

    Example:
        >>> # Text only
        >>> msg = build_user_message("Hello")
        >>> # {"role": "user", "content": "Hello"}

        >>> # Text with PDF
        >>> msg = build_user_message("What is this?", pdf_base64="JVBERi...")
        >>> # {"role": "user", "content": [{"type": "input_file", ...}, {"type": "input_text", ...}]}
    """
    if pdf_base64:
        # Message with PDF attachment (Responses API format)
        logger.debug(f"Building user message with PDF attachment (filename: {filename})")
        return {
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "filename": filename,
                    "file_data": f"data:application/pdf;base64,{pdf_base64}",
                },
                {
                    "type": "input_text",
                    "text": text,
                },
            ],
        }
    else:
        # Simple text message
        logger.debug("Building simple text user message")
        return {
            "role": "user",
            "content": text,
        }


def build_assistant_message(text: str) -> Dict[str, Any]:
    """
    Build an assistant message.

    Args:
        text: Assistant's response text

    Returns:
        Message dictionary in Responses API format

    Example:
        >>> msg = build_assistant_message("The answer is 42")
        >>> # {"role": "assistant", "content": "The answer is 42"}
    """
    logger.debug("Building assistant message")
    return {
        "role": "assistant",
        "content": text,
    }


def patch_message_with_pdf(message_text: str, pdf_base64: str, filename: str = "document.pdf") -> Dict[str, Any]:
    """
    Patch a text message to include a PDF file.

    This is a convenience function that creates a user message with PDF.
    Useful for context window patching when adding PDFs to existing messages.

    Args:
        message_text: Original message text
        pdf_base64: Base64-encoded PDF string
        filename: PDF filename (default: "document.pdf")

    Returns:
        Patched message dictionary with PDF attachment

    Example:
        >>> patched = patch_message_with_pdf("What is this?", "JVBERi...")
        >>> # Returns user message with both PDF and text
    """
    logger.debug(f"Patching message with PDF (filename: {filename})")
    return build_user_message(text=message_text, pdf_base64=pdf_base64, filename=filename)


def build_message_history(
    messages_data: List[Dict[str, Any]],
    pdf_base64_map: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Build message history with optional PDF patching.

    Takes a list of message data and optionally patches PDFs into specific messages.

    Args:
        messages_data: List of message dictionaries with keys:
                       - role: "user" or "assistant"
                       - content: message text
                       - pdf_base64: (optional) base64 PDF to attach
        pdf_base64_map: Optional dict mapping message index to PDF base64
                        (alternative to including pdf_base64 in messages_data)

    Returns:
        List of properly formatted messages for Responses API

    Example:
        >>> messages = [
        ...     {"role": "user", "content": "Hello", "pdf_base64": "JVBERi..."},
        ...     {"role": "assistant", "content": "Hi there!"},
        ...     {"role": "user", "content": "What about page 2?"}
        ... ]
        >>> history = build_message_history(messages)
        >>> # First message will have PDF attached, others won't
    """
    logger.debug(f"Building message history with {len(messages_data)} messages")

    formatted_messages = []

    for idx, msg_data in enumerate(messages_data):
        role = msg_data.get("role")
        content = msg_data.get("content")

        if role == "user":
            # Check for PDF in message data or map
            pdf_base64 = msg_data.get("pdf_base64")
            if pdf_base64_map and idx in pdf_base64_map:
                pdf_base64 = pdf_base64_map[idx]

            # Build user message with optional PDF
            formatted_msg = build_user_message(
                text=content,
                pdf_base64=pdf_base64,
                filename=msg_data.get("filename", "document.pdf")
            )
            formatted_messages.append(formatted_msg)

        elif role == "assistant":
            # Build assistant message
            formatted_msg = build_assistant_message(content)
            formatted_messages.append(formatted_msg)

        else:
            logger.warning(f"Unknown message role: {role}. Skipping message.")

    logger.debug(f"Built {len(formatted_messages)} formatted messages")
    return formatted_messages
