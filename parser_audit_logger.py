# audit_logger.py
import os, json, uuid, datetime
from typing import Optional, Dict, Any
import re

class AuditLogger:
    def __init__(self, actor: str, role: str, schema_version: str,
                 parser_version: str, log_path: str):
        self.actor = actor
        self.role = role
        self.schema_version = schema_version
        self.parser_version = parser_version
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    @staticmethod
    def _ts() -> str:
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    def _write(self, payload: Dict[str, Any]):
        # Ensure required common fields exist
        payload.setdefault("schema_version", self.schema_version)
        payload.setdefault("parser_version", self.parser_version)
        payload.setdefault("meta", {})
        with open(self.log_path, "a", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write("\n")

    def parse_start(self, run_id: str, doc_id: str, meta: Optional[Dict[str, Any]] = None):
        self._write({
            "timestamp": self._ts(),
            "run_id": run_id,
            "doc_id": doc_id,
            "actor": self.actor,
            "role": self.role,
            "action": "parse_start",
            "field": None,
            "from": None,
            "to": None,
            "status": "success",
            "meta": meta or {}
        })

    def auto_extract_parser(self, run_id: str, doc_id: str, field: str,
                            to_value: Any, status: str = "success",
                            meta: Optional[Dict[str, Any]] = None):
        self._write({
            "timestamp": self._ts(),
            "run_id": run_id,
            "doc_id": doc_id,
            "actor": self.actor,
            "role": self.role,
            "action": "auto_extract_parser",
            "field": field,
            "from": None,
            "to": to_value,
            "status": status,  # "success" | "fail"
            "meta": meta or {}
        })

    def normalize_field(self, run_id: str, doc_id: str, field: str,
                        from_value: Any, to_value: Any,
                        meta: Optional[Dict[str, Any]] = None):
        # use status "corrected" when normalization changes value
        self._write({
            "timestamp": self._ts(),
            "run_id": run_id,
            "doc_id": doc_id,
            "actor": self.actor,
            "role": self.role,
            "action": "normalize_field",
            "field": field,
            "from": from_value,
            "to": to_value,
            "status": "corrected" if (to_value is not None and to_value != from_value) else "success",
            "meta": meta or {}
        })

    def parse_end(self, run_id: str, doc_id: str,
                  fields_extracted_count: int,
                  required_total: Optional[int] = None,
                  status: str = "success",
                  meta: Optional[Dict[str, Any]] = None):
        m = meta.copy() if meta else {}
        m.update({
            "fields_extracted_count": fields_extracted_count,
            "required_total": required_total
        })
        self._write({
            "timestamp": self._ts(),
            "run_id": run_id,
            "doc_id": doc_id,
            "actor": self.actor,
            "role": self.role,
            "action": "parse_end",
            "field": None,
            "from": None,
            "to": None,
            "status": "success",
            "meta": {"fields_extracted_count": fields_extracted_count,
                     "required_total": required_total, **(meta or {})}
        })


# Exported utility
def iso_yyyymmdd(s: Optional[str]) -> Optional[str]:
    """Best-effort normalize to YYYY-MM-DD."""
    if not s:
        return None
    s = s.strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return s  # already ISO
    # MM/DD/YY(YY)
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", s)
    if m:
        mm, dd, yy = m.groups()
        yy = int(yy)
        if yy < 100:
            yy = 2000 + yy if yy <= 69 else 1900 + yy
        try:
            return datetime.date(int(yy), int(mm), int(dd)).isoformat()
        except ValueError:
            return None
    # YYYY/MM/DD
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m:
        yyyy, mm, dd = m.groups()
        try:
            return datetime.date(int(yyyy), int(mm), int(dd)).isoformat()
        except ValueError:
            return None
    return None