"""Small shared contracts for cross-language discovery and lifecycle evidence."""

from .lifecycle import TerminalOutcome
from .profile import LanguageProfile, ProfileError, load_profile, load_profiles

__all__ = [
    "LanguageProfile",
    "ProfileError",
    "TerminalOutcome",
    "load_profile",
    "load_profiles",
]
