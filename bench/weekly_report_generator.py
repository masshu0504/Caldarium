"""
Weekly Report Generator for Caldarium Intake Agent
Generates compliance reports for stakeholders (Matthew/Jay)
"""
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from audit_logger import AuditLogger

class WeeklyReportGenerator:
    def __init__(self, audit_log_file: str = "audit_log.jsonl"):
        """
        Initialize weekly report generator
        
        Args:
            audit_log_file: Path to audit log file
        """
        self.audit_log_file = Path(audit_log_file)
        self.report_data = {}
    
    def load_audit_data(self, days_back: int = 7) -> pd.DataFrame:
        """Load audit data from the last N days"""
        if not self.audit_log_file.exists():
            return pd.DataFrame()
        
        # Read JSONL file
        logs = []
        with open(self.audit_log_file, 'r') as f:
            for line in f:
                try:
                    logs.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        
        if not logs:
            return pd.DataFrame()
        
        df = pd.DataFrame(logs)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Filter to last N days
        cutoff_date = datetime.now() - timedelta(days=days_back)
        df = df[df['timestamp'] >= cutoff_date]
        
        return df
    
    def calculate_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate key metrics from audit data"""
        if df.empty:
            return {
                "total_documents": 0,
                "total_operations": 0,
                "success_rate": 0,
                "schema_pass_rate": 0,
                "critical_field_f1": 0,
                "error_breakdown": {},
                "stage_performance": {},
                "notes": "No data available for this period"
            }
        
        # Basic counts
        total_documents = df['doc_id'].nunique()
        total_operations = len(df)
        
        # Success rate
        success_count = len(df[df['error_type'] == 'SUCCESS'])
        success_rate = (success_count / total_operations * 100) if total_operations > 0 else 0
        
        # Schema pass rate (documents with no SCHEMA_MISMATCH errors)
        schema_failures = df[df['error_type'] == 'SCHEMA_MISMATCH']['doc_id'].nunique()
        schema_pass_rate = ((total_documents - schema_failures) / total_documents * 100) if total_documents > 0 else 0
        
        # Critical field F1 score (invoice_number, patient_id, total_amount)
        critical_fields = ['invoice_number', 'patient_id', 'total_amount']
        field_scores = {}
        
        for field in critical_fields:
            # Count documents where this field was successfully extracted
            field_success = 0
            for doc_id in df['doc_id'].unique():
                doc_ops = df[df['doc_id'] == doc_id]
                # Check if field was extracted successfully
                field_extracted = any(
                    'extracted_fields' in str(details) and field in str(details)
                    for details in doc_ops['details']
                )
                if field_extracted:
                    field_success += 1
            
            field_scores[field] = (field_success / total_documents * 100) if total_documents > 0 else 0
        
        # Average F1 across critical fields
        critical_field_f1 = sum(field_scores.values()) / len(critical_fields) if critical_fields else 0
        
        # Error breakdown
        error_breakdown = df['error_type'].value_counts().to_dict()
        
        # Stage performance
        stage_performance = {}
        for stage in df['stage'].unique():
            stage_df = df[df['stage'] == stage]
            stage_success = len(stage_df[stage_df['error_type'] == 'SUCCESS'])
            stage_performance[stage] = {
                'total_operations': len(stage_df),
                'success_rate': (stage_success / len(stage_df) * 100) if len(stage_df) > 0 else 0
            }
        
        return {
            "total_documents": total_documents,
            "total_operations": total_operations,
            "success_rate": round(success_rate, 2),
            "schema_pass_rate": round(schema_pass_rate, 2),
            "critical_field_f1": round(critical_field_f1, 2),
            "field_scores": field_scores,
            "error_breakdown": error_breakdown,
            "stage_performance": stage_performance,
            "notes": self._generate_notes(error_breakdown, stage_performance)
        }
    
    def _generate_notes(self, error_breakdown: Dict, stage_performance: Dict) -> str:
        """Generate human-readable notes based on metrics"""
        notes = []
        
        # Error analysis
        if 'EXTRACTION_FAIL' in error_breakdown:
            notes.append(f"EXTRACTION_FAIL: {error_breakdown['EXTRACTION_FAIL']} occurrences - investigate PDF quality")
        
        if 'MISSING_FIELD' in error_breakdown:
            notes.append(f"MISSING_FIELD: {error_breakdown['MISSING_FIELD']} occurrences - improve regex patterns")
        
        if 'TABLE_EXTRACTION_FAIL' in error_breakdown:
            notes.append(f"TABLE_EXTRACTION_FAIL: {error_breakdown['TABLE_EXTRACTION_FAIL']} occurrences - debug table detection")
        
        # Performance analysis
        for stage, perf in stage_performance.items():
            if perf['success_rate'] < 80:
                notes.append(f"{stage} stage: {perf['success_rate']:.1f}% success rate - needs attention")
        
        if not notes:
            notes.append("All systems performing within acceptable parameters")
        
        return "; ".join(notes)
    
    def generate_report(self, output_file: str = None, days_back: int = 7) -> Dict[str, Any]:
        """Generate the weekly report"""
        df = self.load_audit_data(days_back)
        metrics = self.calculate_metrics(df)
        
        report = {
            "report_period": f"Last {days_back} days",
            "generated_at": datetime.now().isoformat(),
            "metrics": metrics,
            "recommendations": self._generate_recommendations(metrics)
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report
    
    def _generate_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on metrics"""
        recommendations = []
        
        if metrics['success_rate'] < 90:
            recommendations.append("Improve overall parsing success rate - focus on most common error types")
        
        if metrics['schema_pass_rate'] < 95:
            recommendations.append("Address schema validation issues - review field extraction patterns")
        
        if metrics['critical_field_f1'] < 80:
            recommendations.append("Enhance critical field extraction - prioritize invoice_number, patient_id, total_amount")
        
        if 'MISSING_FIELD' in metrics['error_breakdown']:
            recommendations.append("Develop more robust regex patterns for missing fields")
        
        if 'TABLE_EXTRACTION_FAIL' in metrics['error_breakdown']:
            recommendations.append("Investigate table extraction alternatives or improve current methods")
        
        if not recommendations:
            recommendations.append("Continue current optimization efforts - system performing well")
        
        return recommendations

def generate_weekly_report(audit_log_file: str = "audit_log.jsonl", 
                          output_file: str = "weekly_report.json",
                          days_back: int = 7) -> Dict[str, Any]:
    """Convenience function to generate weekly report"""
    generator = WeeklyReportGenerator(audit_log_file)
    return generator.generate_report(output_file, days_back)

if __name__ == "__main__":
    # Generate sample report
    report = generate_weekly_report()
    print("Weekly Report Generated:")
    print(json.dumps(report, indent=2))
