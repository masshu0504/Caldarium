from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

class ErrorCode(str, Enum):
    EXTRACTION_FAIL = "EXTRACTION_FAIL"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    MISSING_FIELD = "MISSING_FIELD"
    OCR_NOISE = "OCR_NOISE"

class Stage(str, Enum):
    OCR = "OCR"
    PARSER = "PARSER"
    VALIDATOR = "VALIDATOR"
    POSTPROC = "POSTPROC"

@dataclass
class ErrorEvent:
    error_code: ErrorCode
    stage: Stage
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: Optional[Dict[str, str]] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "stage": self.stage.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "source": self.source,
            "details": self.details,
        }
