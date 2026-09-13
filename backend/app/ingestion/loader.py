"""
Transcript loader — clones/pulls the GitHub repo and parses transcript files.

Each transcript is a markdown file with YAML frontmatter containing metadata
(guest, title, youtube_url, publish_date, etc.) and the full transcript body.
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Generator, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class TranscriptDoc:
    """Parsed transcript with metadata and body text."""
    episode_title: str
    guest: str
    youtube_url: Optional[str]
    publish_date: Optional[date]
    body_text: str
    file_path: str


def clone_or_pull(repo_url: str, local_path: str) -> Path:
    """
    Clone the transcript repo if it doesn't exist, otherwise pull latest.
    Returns the Path to the local repo.
    """
    repo_dir = Path(local_path)

    if (repo_dir / ".git").is_dir():
        logger.info("Repo already cloned at %s — pulling latest…", repo_dir)
        subprocess.run(
            ["git", "-C", str(repo_dir), "pull", "--ff-only"],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        logger.info("Cloning %s → %s", repo_url, repo_dir)
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
        )

    return repo_dir


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Split YAML frontmatter from markdown body.
    Returns (metadata_dict, body_text).
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        metadata = {}

    body = parts[2].strip()
    return metadata, body


def _parse_date(raw: object) -> Optional[date]:
    """Safely parse a date from frontmatter (might be str or date)."""
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    return None


def load_transcripts(repo_path: str | Path) -> Generator[TranscriptDoc, None, None]:
    """
    Yield TranscriptDoc for each transcript.md found in the episodes directory.
    """
    episodes_dir = Path(repo_path) / "episodes"
    if not episodes_dir.is_dir():
        logger.error("Episodes directory not found: %s", episodes_dir)
        return

    transcript_files = sorted(episodes_dir.rglob("transcript.md"))
    logger.info("Found %d transcript files", len(transcript_files))

    for fpath in transcript_files:
        try:
            content = fpath.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read %s: %s", fpath, e)
            continue

        metadata, body = _parse_frontmatter(content)

        if not body.strip():
            logger.warning("Empty transcript body: %s", fpath)
            continue

        title = metadata.get("title", fpath.parent.name)
        guest = metadata.get("guest", fpath.parent.name)
        youtube_url = metadata.get("youtube_url")
        publish_date = _parse_date(metadata.get("publish_date"))

        yield TranscriptDoc(
            episode_title=title,
            guest=guest,
            youtube_url=youtube_url,
            publish_date=publish_date,
            body_text=body,
            file_path=str(fpath),
        )
