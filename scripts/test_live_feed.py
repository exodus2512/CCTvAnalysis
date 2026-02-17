import cv2

url = 'http://localhost:8000/live_feed'
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print('Failed to open live feed')
    exit(1)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    cv2.imshow('SentinelAI Live Feed', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()
