#!/usr/bin/env python3
"""
Quick script to run early benchmark from command line
Usage: python run_early_benchmark.py
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from early_benchmark import EarlyBenchmark

def main():
    """Run early benchmark with default configuration"""
    
    print("Starting Early Benchmark...")
    print("=" * 60)
    
    # Create and run benchmark
    benchmark = EarlyBenchmark()
    results = benchmark.run_minimal_benchmark()
    benchmark.results = results
    
    # Save results
    output_file = benchmark.save_results()
    
    # Print summary
    benchmark.print_summary()
    
    print("\n" + "=" * 60)
    print("Early benchmark completed!")
    print(f"Results saved to: {output_file}")
    print(f"Run ID: {benchmark.run_id}")
    print(f"Environment Hash: {benchmark.environment_hash}")
    
    return results

if __name__ == "__main__":
    main()