"""Local meeting capture and transcription.

Raw audio is intentionally never persisted by this package. The browser captures
microphone/system audio on the owner's machine; the API hands one bounded chunk
straight to the already-governed transcription broker and stores only text,
timings and operational metadata.
"""

from .service import MeetingTranscriber, MeetingTranscriptionError
from .store import MeetingError, MeetingStore

__all__ = [
    "MeetingError",
    "MeetingStore",
    "MeetingTranscriber",
    "MeetingTranscriptionError",
]
