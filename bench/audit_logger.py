"""
Audit Logger for Caldarium Intake Agent
Tracks all parsing operations for compliance and debugging
"""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd

class AuditLogger:
    def __init__(self, log_file: str = "audit_log.jsonl", run_id: Optional[str] = None):
        """
        Initialize audit logger
        
        Args:
            log_file: Path to audit log file (JSONL format)
            run_id: Unique identifier for this parsing run
        """
        self.log_file = Path(log_file)
        self.run_id = run_id or self._generate_run_id()
        self.logs = []
    
    def _generate_run_id(self) -> str:
        """Generate a unique run ID based on timestamp and config"""
        timestamp = datetime.now(timezone.utc).isoformat()
        config_hash = hashlib.md5(timestamp.encode()).hexdigest()[:8]
        return f"run_{config_hash}"
    
    def log_operation(self, 
                     doc_id: str,
                     stage: str,
                     error_type: str,
                     details: Dict[str, Any],
                     resolution: str = "unresolved") -> None:
        """
        Log a parsing operation
        
        Args:
            doc_id: Document identifier
            stage: Pipeline stage (parse/validate/postprocess/table_extract)
            error_type: Error type from taxonomy
            details: Detailed operation information
            resolution: How the error was handled
        """
        log_entry = {
            "doc_id": doc_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "error_type": error_type,
            "details": details,
            "resolution": resolution,
            "run_id": self.run_id
        }
        
        self.logs.append(log_entry)
        
        # Write to file immediately (for real-time monitoring)
        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def log_success(self, doc_id: str, stage: str, details: Dict[str, Any]) -> None:
        """Log a successful operation"""
        self.log_operation(doc_id, stage, "SUCCESS", details, "resolved")
    
    def log_error(self, doc_id: str, stage: str, error_type: str, details: Dict[str, Any]) -> None:
        """Log an error operation"""
        self.log_operation(doc_id, stage, error_type, details, "unresolved")
    
    def get_logs_df(self) -> pd.DataFrame:
        """Convert logs to pandas DataFrame for analysis"""
        if not self.logs:
            return pd.DataFrame()
        return pd.DataFrame(self.logs)
    
    def export_logs(self, output_file: str) -> None:
        """Export logs to CSV for analysis"""
        df = self.get_logs_df()
        if not df.empty:
            df.to_csv(output_file, index=False)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for this run"""
        if not self.logs:
            return {}
        
        df = self.get_logs_df()
        
        return {
            "run_id": self.run_id,
            "total_operations": len(df),
            "success_rate": len(df[df["error_type"] == "SUCCESS"]) / len(df) if len(df) > 0 else 0,
            "error_counts": df["error_type"].value_counts().to_dict(),
            "stage_counts": df["stage"].value_counts().to_dict(),
            "resolution_counts": df["resolution"].value_counts().to_dict(),
            "unique_documents": df["doc_id"].nunique(),
            "avg_processing_time": df["details"].apply(
                lambda x: x.get("processing_time_ms", 0) if isinstance(x, dict) else 0
            ).mean()
        }

# Global audit logger instance
audit_logger = AuditLogger()

def log_parsing_operation(doc_id: str, stage: str, error_type: str, details: Dict[str, Any]):
    """Convenience function for logging parsing operations"""
    audit_logger.log_operation(doc_id, stage, error_type, details)

def log_parsing_success(doc_id: str, stage: str, details: Dict[str, Any]):
    """Convenience function for logging successful operations"""
    audit_logger.log_success(doc_id, stage, details)

def log_parsing_error(doc_id: str, stage: str, error_type: str, details: Dict[str, Any]):
    """Convenience function for logging errors"""
    audit_logger.log_error(doc_id, stage, error_type, details)
