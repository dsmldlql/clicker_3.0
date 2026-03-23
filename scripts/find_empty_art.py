#!/usr/bin/env python3
"""
Find JSON documents where norms have empty 'art' but filled 'art_punkt'.
"""

import json
import os
from pathlib import Path
from collections import defaultdict

ANSWERS_DIR = Path(__file__).parent.parent / "answers"


def find_norms_with_empty_art(answers_dir: Path):
    """Find all norms with empty art but non-empty art_punkt."""
    
    results = []
    
    for root, _, files in os.walk(answers_dir):
        for filename in files:
            if not filename.endswith('.json'):
                continue
            
            file_path = Path(root) / filename
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                continue
            
            norms = data.get('Norms', [])
            if not isinstance(norms, list):
                continue
            
            for norm in norms:
                if not isinstance(norm, dict):
                    continue
                
                art = norm.get('art', '')
                art_punkt = norm.get('art_punkt', '')
                
                # Check if art is empty/whitespace but art_punkt has value
                art_empty = not art or str(art).strip() == '' or str(art).strip() == 'null'
                art_punkt_filled = art_punkt and str(art_punkt).strip() != '' and str(art_punkt).strip() != 'null'
                
                if art_empty and art_punkt_filled:
                    results.append({
                        'file': str(file_path),
                        'act': norm.get('act', ''),
                        'art': art,
                        'art_punkt': art_punkt,
                        'date': norm.get('date', ''),
                        'number': norm.get('number', ''),
                    })
    
    return results


def main():
    print("Searching for norms with empty 'art' but filled 'art_punkt'...")
    print(f"Scanning: {ANSWERS_DIR}\n")
    
    results = find_norms_with_empty_art(ANSWERS_DIR)
    
    print(f"Found {len(results)} norms with empty 'art' but filled 'art_punkt'\n")
    
    if results:
        # Group by file
        by_file = defaultdict(list)
        for r in results:
            by_file[r['file']].append(r)
        
        print(f"Across {len(by_file)} files:\n")
        
        for file_path, norms in list(by_file.items())[:10]:  # Show first 10 files
            print(f"File: {file_path}")
            for norm in norms[:5]:  # Show first 5 norms per file
                print(f"  act={norm['act'][:40] if norm['act'] else ''}...")
                print(f"    art='{norm['art']}', art_punkt='{norm['art_punkt']}'")
                print(f"    date={norm['date']}, number={norm['number']}")
            if len(norms) > 5:
                print(f"  ... and {len(norms) - 5} more")
            print()
        
        if len(by_file) > 10:
            print(f"... and {len(by_file) - 10} more files")


if __name__ == "__main__":
    main()
