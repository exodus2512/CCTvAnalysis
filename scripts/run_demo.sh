#!/bin/bash
# SentinelAI Demo Script
# 1. Start backend
# 2. Start AI worker for fight detection
# 3. Start AI worker for other events (optional)
# 4. Start dashboard (in another terminal)

# Start backend
cd ../backend && uvicorn main:app --reload &
# Start AI worker (fight)
cd ../ai_worker && python worker.py worker fight &
# Start AI worker (fire/smoke)
python worker.py worker fire_smoke &
# Start AI worker (intrusion)
python worker.py worker intrusion &
# Start AI worker (abandoned_object)
python worker.py worker abandoned_object &
# Start AI worker (gate_accident)
python worker.py worker gate_accident &
# Start AI worker (exam_malpractice)
python worker.py worker exam_malpractice &
# Dashboard: run in another terminal
# cd ../dashboard && npm run dev
