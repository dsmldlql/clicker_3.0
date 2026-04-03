#!/usr/bin/env python3
"""
Test script for region-based template matching.
"""

import cv2
import numpy as np
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.gpu_analyzer import GPUAnalyzer

def test_region_matching():
    """Test that region-based matching works correctly."""
    
    analyzer = GPUAnalyzer()
    
    # Create a test frame (simulating a 1920x1080 screen)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    
    # Draw a white rectangle in the bottom-right area (simulating more.png)
    # This is at position (1700, 800) with size 100x100
    cv2.rectangle(frame, (1700, 800), (1800, 900), (255, 255, 255), -1)
    # Add some text to make it unique
    cv2.putText(frame, "MORE", (1710, 850), cv2.FONT_HERSHEY_SIMPLEX, 
                1, (255, 255, 255), 2)
    
    # Draw a similar rectangle elsewhere (simulating the confusing similar button)
    cv2.rectangle(frame, (500, 400), (600, 500), (255, 255, 255), -1)
    cv2.putText(frame, "MORE2", (510, 450), cv2.FONT_HERSHEY_SIMPLEX, 
                1, (255, 255, 255), 2)
    
    # Create a simple template (white square)
    template_path = "/tmp/test_more_template.png"
    template = np.zeros((100, 100), dtype=np.uint8)
    cv2.rectangle(template, (0, 0), (100, 100), (255, 255, 255), -1)
    cv2.imwrite(template_path, template)
    
    print("Test 1: Search entire frame (no region)")
    coords1, score1 = analyzer.find_best_match(
        frame,
        [template_path],
        0.7
    )
    print(f"  Result: coords={coords1}, score={score1}")
    assert coords1 is not None, "Should find template in full frame"
    print("  ✓ PASSED")
    
    print("\nTest 2: Search with region including the target")
    coords2, score2 = analyzer.find_best_match(
        frame,
        [template_path],
        0.7,
        region=(1600, 700, 300, 300)  # Region around (1700, 800)
    )
    print(f"  Result: coords={coords2}, score={score2}")
    assert coords2 is not None, "Should find template in specified region"
    # Coordinates should be relative to full frame, so x should be around 1700+
    assert coords2[0] > 1600, f"X coordinate should be in region, got {coords2[0]}"
    print("  ✓ PASSED")
    
    print("\nTest 3: Search with region EXCLUDING the target")
    coords3, score3 = analyzer.find_best_match(
        frame,
        [template_path],
        0.7,
        region=(0, 0, 400, 400)  # Top-left area, away from both rectangles
    )
    print(f"  Result: coords={coords3}, score={score3}")
    assert coords3 is None, "Should NOT find template outside region"
    print("  ✓ PASSED")
    
    print("\nTest 4: Search with region excluding target but including distractor")
    coords4, score4 = analyzer.find_best_match(
        frame,
        [template_path],
        0.7,
        region=(400, 300, 300, 300)  # Region around the distractor at (500, 400)
    )
    print(f"  Result: coords={coords4}, score={score4}")
    # Should find the distractor since it's in the region
    if coords4 is not None:
        assert 400 <= coords4[0] <= 700, f"Should find distractor, got x={coords4[0]}"
        print("  ✓ PASSED (found distractor as expected)")
    else:
        print("  ✓ PASSED (distractor not similar enough)")
    
    # Cleanup
    if os.path.exists(template_path):
        os.remove(template_path)
    
    print("\n" + "="*50)
    print("All tests passed! ✓")
    print("="*50)

if __name__ == "__main__":
    test_region_matching()
