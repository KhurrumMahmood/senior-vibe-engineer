"""Small shared contracts for cross-language discovery."""

from .profile import LanguageProfile, ProfileError, load_profile, load_profiles

__all__ = [
    "LanguageProfile",
    "ProfileError",
    "load_profile",
    "load_profiles",
]
