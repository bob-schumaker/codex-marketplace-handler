from __future__ import annotations

import re


__all__ = ["display_name_from_slug", "normalize_slug", "normalize_whitespace"]


def normalize_slug(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    normalized = re.sub(r"[^a-z0-9-]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def display_name_from_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in normalize_slug(value).split("-"))


def split_sentences(value: str) -> list[str]:
    text = normalize_whitespace(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def first_sentence(value: str) -> str:
    sentences = split_sentences(value)
    if not sentences:
        return normalize_whitespace(value)
    return sentences[0]


def extract_trigger_phrases(value: str) -> list[str]:
    seen: set[str] = set()
    triggers: list[str] = []
    for match in re.finditer(r'"([^"]+)"|`([^`]+)`', value):
        phrase = match.group(1) or match.group(2) or ""
        cleaned = normalize_whitespace(phrase).strip(".,;: ")
        if not cleaned:
            continue
        if match.group(2) and "/" not in cleaned and " " not in cleaned:
            continue
        normalized = cleaned.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        triggers.append(cleaned)
    return triggers


def join_human_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def truncate_sentence(value: str, limit: int = 240) -> str:
    text = normalize_whitespace(value)
    if len(text) <= limit:
        return text
    head = text[: limit - 1].rstrip()
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return f"{head}…"


def strip_terminal_punctuation(value: str) -> str:
    return value.rstrip(" .!?")


def collect_semantic_summaries(module_descriptions: list[str]) -> list[str]:
    summaries: list[str] = []
    seen_summaries: set[str] = set()
    for description in module_descriptions:
        summary = first_sentence(description)
        normalized = summary.casefold()
        if not summary or normalized in seen_summaries:
            continue
        seen_summaries.add(normalized)
        summaries.append(summary)
    return summaries


def collect_trigger_phrases(
    module_descriptions: list[str], limit: int = 3
) -> list[str]:
    trigger_phrases: list[str] = []
    seen_triggers: set[str] = set()
    for description in module_descriptions:
        for trigger in extract_trigger_phrases(description):
            normalized = trigger.casefold()
            if normalized in seen_triggers:
                continue
            seen_triggers.add(normalized)
            trigger_phrases.append(trigger)
            if len(trigger_phrases) == limit:
                return trigger_phrases
    return trigger_phrases


def render_template_text(template_text: str, parameters: dict[str, object]) -> str:
    rendered = template_text
    for key, value in sorted(parameters.items()):
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered
