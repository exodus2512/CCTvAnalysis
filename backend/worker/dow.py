# download_models.py
# Run from your ai_worker/ directory
# python download_models.py

import os
import shutil
from ultralytics import YOLO
from huggingface_hub import hf_hub_download

os.makedirs("models", exist_ok=True)

# ─────────────────────────────────────────────
# 1. Standard YOLO base models (auto-downloads via ultralytics)
# ─────────────────────────────────────────────
print("Downloading base YOLO models...")
for model_name in ["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8n-pose.pt"]:
    m = YOLO(model_name)  # downloads to ~/.ultralytics cache
    src = m.ckpt_path
    dst = f"models/{model_name}"
    shutil.copy(src, dst)
    print(f"  ✓ {model_name}")

# ─────────────────────────────────────────────
# 2. Fire + Smoke model (public, no auth required)
#    Repo: Notacodinggeek/yolov8n-fire-smoke
#    Classes: fire, smoke
# ─────────────────────────────────────────────
print("\nDownloading fire/smoke model...")
try:
    path = hf_hub_download(
        repo_id="Notacodinggeek/yolov8n-fire-smoke",
        filename="best.pt"
    )
    shutil.copy(path, "models/fire_smoke_model.pt")
    print("  ✓ fire_smoke_model.pt")
except Exception as e:
    print(f"  ✗ Primary failed: {e}")
    print("  Trying fallback: touati-kamel/yolov8s-forest-fire-detection ...")
    try:
        path = hf_hub_download(
            repo_id="touati-kamel/yolov8s-forest-fire-detection",
            filename="best.pt"
        )
        shutil.copy(path, "models/fire_smoke_model.pt")
        print("  ✓ fire_smoke_model.pt (fallback)")
    except Exception as e2:
        print(f"  ✗ Fallback also failed: {e2}")
        print("  ⚠ Will use COCO-based heuristic fallback in fire_smoke_detector")

# ─────────────────────────────────────────────
# 3. Weapon model — GUN detection
#    Repo: Subh775/Firearm_Detection_Yolov8n
#    Public, no auth. mAP@0.5 = 89%
#    Classes: Gun
# ─────────────────────────────────────────────
print("\nDownloading gun/firearm model...")
try:
    path = hf_hub_download(
        repo_id="Subh775/Firearm_Detection_Yolov8n",
        filename="weights/best.pt"
    )
    shutil.copy(path, "models/gun_model.pt")
    print("  ✓ gun_model.pt  (89% mAP, detects: Gun)")
except Exception as e:
    print(f"  ✗ Failed: {e}")

# ─────────────────────────────────────────────
# 4. Threat model — GUN + GRENADE (broader)
#    Repo: Subh775/Threat-Detection-YOLOv8n
#    Public, no auth. Gun: 96.7%, Grenade: 93.1%
#    Classes: Gun, Grenade, Knife (multi-class)
# ─────────────────────────────────────────────
print("\nDownloading multi-threat model (gun+knife+grenade)...")
try:
    path = hf_hub_download(
        repo_id="Subh775/Threat-Detection-YOLOv8n",
        filename="weights/best.pt"
    )
    shutil.copy(path, "models/weapon_model.pt")
    print("  ✓ weapon_model.pt  (Gun 96.7%, Grenade 93.1%)")
except Exception as e:
    print(f"  ✗ Failed: {e}")
    print("  ⚠ Will fall back to COCO knife(43)+scissors(76) only")

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
print("\n─── models/ contents ───")
for f in sorted(os.listdir("models")):
    size_mb = os.path.getsize(f"models/{f}") / 1e6
    print(f"  {f:<30} {size_mb:.1f} MB")

print("\nDone! Verify each model with:")
print("  python -c \"from ultralytics import YOLO; m=YOLO('models/weapon_model.pt'); print(m.names)\"")