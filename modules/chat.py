"""
VISION AI - Conversational AI Engine & Multi-Turn Dialogue Manager
Connects to local Ollama LLM, supports streaming token generation, maintains
contextual dialogue memory (pronoun resolution, follow-up queries), and handles
dynamic response modes (Normal, Detailed, Entertainment).
"""

import re
import threading
from typing import Generator, List, Dict, Any, Tuple, Optional


# Mode detection regexes
DETAILED_MODE_RE = re.compile(
    r"\b(?:explain in detail|detailed explanation|elaborate|step by step|deep dive|"
    r"explain thoroughly|give me a detailed|breakdown of|in depth|comprehensive overview|"
    r"vistaar se|detail me|detail mein)\b",
    re.I
)

ENTERTAINMENT_MODE_RE = re.compile(
    r"\b(?:tell me a joke|tell a joke|joke sunao|another joke|funny joke|"
    r"tell me a story|tell a story|kahani sunao|sci-fi story|short story|"
    r"tell me a fact|interesting fact|surprising fact|fun fact|tell me something interesting)\b",
    re.I
)


def detect_conversation_mode(text: str) -> str:
    """
    Classifies the user's conversational intent into:
    - 'detailed': when thorough, step-by-step depth is requested.
    - 'entertainment': when jokes, stories, or fun facts are requested.
    - 'normal': default concise, natural spoken voice response (2-4 sentences).
    """
    raw = text.strip()
    if DETAILED_MODE_RE.search(raw):
        return "detailed"
    if ENTERTAINMENT_MODE_RE.search(raw):
        return "entertainment"
    return "normal"


def build_system_prompt(assistant_name: str = "Vision",
                        creator_name: str = "Taha",
                        mode: str = "normal",
                        user_name: str = "",
                        notes: Optional[List[str]] = None) -> str:
    """
    Constructs an optimized system prompt tailored to the assistant persona, creator attribution,
    and current conversational mode. Enforces natural spoken dialogue without TTS-disrupting markdown.
    """
    notes_str = "; ".join(notes[-5:]) if notes else "None"
    system_base = (
        f"You are {assistant_name}, a highly intelligent, articulate, responsive, and natural conversational AI assistant "
        f"created by {creator_name}. Address the user respectfully as Sir.\n"
        f"User name: {user_name or 'Sir'}\n"
        f"Important user notes: {notes_str}\n\n"
        "Core Conversational Directives:\n"
        "1. You are a true general-purpose conversational AI. Answer questions thoroughly and naturally across "
        "programming, computer science, mathematics, science, technology, history, general knowledge, storytelling, and casual conversation.\n"
        "2. CONTEXT & FOLLOW-UPS: Pay close attention to previous dialogue turns. Understand when the user asks follow-up questions "
        "such as 'Why?', 'Explain that again', 'Give me an example', 'Make it shorter', or 'How does that work?'. Connect your answers seamlessly.\n"
        "3. EXPLANATIONS & EXAMPLES: When asked for an example, provide a concrete, illustrative example immediately. "
        "When explaining technical or programming topics, break down concepts clearly and intuitively.\n"
        "4. SPOKEN VOICE COMPLIANCE: Your responses are voiced aloud via text-to-speech. "
        "NEVER output raw markdown bullet points (- item), asterisks (**bold**), or markdown tables. "
        "Speak in smooth, natural, human-sounding sentences.\n"
    )

    if mode == "detailed":
        system_base += (
            "\nCurrent Mode: DETAILED EXPLANATION.\n"
            "Provide a comprehensive, in-depth, step-by-step breakdown. "
            "Cover core principles, practical examples, and underlying mechanics in clear spoken paragraphs."
        )
    elif mode == "entertainment":
        system_base += (
            "\nCurrent Mode: ENTERTAINMENT.\n"
            "Deliver an engaging, creative story, a witty joke, a fascinating riddle, or a fun fact with personality and flair."
        )
    else:  # normal
        system_base += (
            "\nCurrent Mode: CONVERSATIONAL ASSISTANT.\n"
            "Deliver an articulate, complete, and engaging response (3 to 6 sentences). "
            "Directly answer the question, give context or examples when useful, and remain conversational."
        )

    return system_base


def prepare_chat_messages(user_prompt: str,
                          context: Any,
                          memory: Dict[str, Any],
                          assistant_name: str = "Vision",
                          creator_name: str = "Taha") -> Tuple[str, List[Dict[str, str]]]:
    """
    Prepares multi-turn dialogue messages for Ollama, preserving recent turns
    for pronoun resolution and contextual continuity.
    """
    mode = detect_conversation_mode(user_prompt)
    user_name = memory.get("name", "") if isinstance(memory, dict) else ""
    notes = memory.get("notes", []) if isinstance(memory, dict) else []

    system_prompt = build_system_prompt(
        assistant_name=assistant_name,
        creator_name=creator_name,
        mode=mode,
        user_name=user_name,
        notes=notes
    )

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    # 1. Inject recent turns from ConversationContext (up to 6 turns for rich conversational memory)
    turns_injected = 0
    if hasattr(context, "turns") and context.turns:
        for turn in context.turns[-6:]:
            u = turn.get("user", "").strip()
            v = turn.get("vision", "").strip()
            if u and v:
                messages.append({"role": "user", "content": u})
                messages.append({"role": "assistant", "content": v})
                turns_injected += 1

    # 2. If context turns were empty, fallback to persistent memory conversation history
    if turns_injected == 0 and isinstance(memory, dict):
        hist = memory.get("last_conversation", [])
        for item in hist[-4:]:
            if isinstance(item, dict) and "user" in item and "vision" in item:
                messages.append({"role": "user", "content": item["user"]})
                messages.append({"role": "assistant", "content": item["vision"]})

    # 3. Append current user prompt
    messages.append({"role": "user", "content": user_prompt})

    return mode, messages


def stream_ollama_tokens(ollama_client: Any,
                         model_name: str,
                         messages: List[Dict[str, str]],
                         cancel_event: Optional[threading.Event] = None,
                         max_tokens: int = 350) -> Generator[str, None, None]:
    """
    Streams tokens from local Ollama chat API.
    Terminates immediately if cancel_event is set.
    """
    try:
        response_stream = ollama_client.chat(
            model=model_name,
            messages=messages,
            stream=True,
            options={
                "temperature": 0.7,
                "num_predict": max_tokens,
            }
        )

        for chunk in response_stream:
            if cancel_event is not None and cancel_event.is_set():
                break
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content

    except Exception as e:
        if not cancel_event.is_set():
            err_msg = str(e).lower()
            if "not found" in err_msg:
                yield f"Sir, the model {model_name} is not downloaded yet. Please run ollama pull {model_name} in your terminal."
            elif "connection" in err_msg or "failed to connect" in err_msg or "winerror 10013" in err_msg:
                yield "Sir, I cannot reach the local Ollama service. Please make sure Ollama is running."
            else:
                yield f"Sir, I encountered an error communicating with Ollama: {e}"
