"""
Diagnostic script to test weapon detection on school ground video.

Run: python diagnose_school_ground.py

This checks:
1. If the weapon model loads correctly
2. If it detects anything in Weapon_sch.mp4
3. Compares detection rates across all school videos
"""

import os
import sys
import cv2
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registry import get_model_registry
from detectors import WeaponDetector

def analyze_video(video_path: str, weapon_detector: WeaponDetector, max_frames: int = 100) -> dict:
    """Analyze a video for weapon detections."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open video: {video_path}"}
    
    results = {
        "path": video_path,
        "name": Path(video_path).name,
        "total_frames": 0,
        "frames_with_weapons": 0,
        "total_detections": 0,
        "detections_by_class": {},
        "max_confidence": 0.0,
        "confidence_samples": [],
    }
    
    frame_count = 0
    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        
        results["total_frames"] += 1
        
        # Run weapon detection
        detections = weapon_detector.detect(frame)
        
        if detections:
            results["frames_with_weapons"] += 1
            results["total_detections"] += len(detections)
            
            for det in detections:
                class_name = det.get("class_name", "unknown")
                conf = det.get("confidence", 0.0)
                
                # Track by class
                if class_name not in results["detections_by_class"]:
                    results["detections_by_class"][class_name] = 0
                results["detections_by_class"][class_name] += 1
                
                # Track max confidence
                if conf > results["max_confidence"]:
                    results["max_confidence"] = conf
                
                # Sample some confidence values
                if len(results["confidence_samples"]) < 20:
                    results["confidence_samples"].append(round(conf, 2))
        
        frame_count += 1
    
    cap.release()
    
    # Compute rate
    if results["total_frames"] > 0:
        results["detection_rate"] = results["frames_with_weapons"] / results["total_frames"]
    else:
        results["detection_rate"] = 0.0
    
    return results


def main():
    print("=" * 60)
    print("SCHOOL GROUND WEAPON DETECTION DIAGNOSTIC")
    print("=" * 60)
    
    # Initialize weapon detector
    print("\n[1] Loading weapon detector...")
    registry = get_model_registry()
    weapon_detector = WeaponDetector(registry)
    
    # Check if models are loaded
    print(f"  Weapon model loaded: {weapon_detector._weapon_model is not None}")
    print(f"  Gun model loaded:    {weapon_detector._gun_model is not None}")
    print(f"  Detector disabled:   {weapon_detector._disabled}")
    
    if weapon_detector._weapon_model is None and weapon_detector._gun_model is None:
        print("\n[ERROR] No weapon models available! Check models/ directory.")
        return
    
    # Find test videos
    test_videos_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../test_videos/school"))
    print(f"\n[2] Scanning test videos in: {test_videos_dir}")
    
    if not os.path.isdir(test_videos_dir):
        print(f"[ERROR] Directory not found: {test_videos_dir}")
        return
    
    video_files = []
    for ext in ["*.mp4", "*.avi", "*.mov"]:
        import glob
        video_files.extend(glob.glob(os.path.join(test_videos_dir, ext)))
    
    print(f"  Found {len(video_files)} videos")
    
    # Analyze each video
    print(f"\n[3] Analyzing videos (first 100 frames each)...")
    
    for video_path in sorted(video_files):
        print(f"\n  --- {Path(video_path).name} ---")
        results = analyze_video(video_path, weapon_detector, max_frames=100)
        
        if "error" in results:
            print(f"    ERROR: {results['error']}")
            continue
        
        print(f"    Frames analyzed:     {results['total_frames']}")
        print(f"    Frames with weapons: {results['frames_with_weapons']}")
        print(f"    Detection rate:      {results['detection_rate']:.1%}")
        print(f"    Total detections:    {results['total_detections']}")
        print(f"    Max confidence:      {results['max_confidence']:.2f}")
        print(f"    By class:            {results['detections_by_class']}")
        
        if results["confidence_samples"]:
            print(f"    Sample confidences:  {results['confidence_samples'][:10]}")
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)
    print("""
If Weapon_sch.mp4 shows 0 detections but fight_school.mp4 shows many:
- The weapon model doesn't recognize objects in Weapon_sch.mp4
- Consider: the video may not contain weapons the model can detect

Possible fixes:
1. Lower detection threshold (currently 0.45 for school_ground)
2. Use a different video with clearer weapons
3. Retrain the weapon model to recognize the weapon types in this video
4. Switch the school_ground camera to use zone="all" for multi-zone detection
""")


if __name__ == "__main__":
    main()
