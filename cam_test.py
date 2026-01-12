from picamera2 import Picamera2
import time

picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration())

picam2.start()
time.sleep(1)  # let exposure/awb settle
picam2.capture_file("snap.jpg")
picam2.stop()

print("Wrote snap.jpg")