"""Structured console + file logging for agent pipeline steps."""

import logging

logger = logging.getLogger("brieflyy.agents")


def log_agent_start(agent_name: str, detail: str = "") -> None:
    message = f"[Brieflyy] {agent_name} started"
    if detail:
        message += f" — {detail}"
    print(message, flush=True)
    logger.info(message)


def log_agent_complete(agent_name: str, detail: str = "") -> None:
    message = f"[Brieflyy] {agent_name} complete"
    if detail:
        message += f" — {detail}"
    print(message, flush=True)
    logger.info(message)


def log_agent_error(agent_name: str, error: str) -> None:
    message = f"[Brieflyy] {agent_name} FAILED — {error}"
    print(message, flush=True)
    logger.error(message)
