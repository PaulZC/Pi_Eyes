#!/usr/bin/python

# Network crazy eyes : Server
#
# A remix of:
#
# Adafruit / Phillip Burgess (Paint Your Dragon)'s Animated Snake Eyes for Raspberry Pi
# https://learn.adafruit.com/animated-snake-eyes-bonnet-for-raspberry-pi/software-installation
# https://github.com/adafruit/Pi_Eyes
#
# Nathan Jennings / Real Python guide to Socket Programming in Python (Guide)
# https://realpython.com/python-sockets/#handling-multiple-connections
# https://github.com/realpython/materials/blob/master/python-sockets-tutorial/multiconn-server.py
#
# Adrian Rosebrock's motion detection tutorial
# https://www.pyimagesearch.com/2015/06/01/home-surveillance-and-motion-detection-with-the-raspberry-pi-python-and-opencv/

# Installing OpenCV:
# sudo apt-get install libhdf5-dev -y && sudo apt-get install libhdf5-serial-dev -y && sudo apt-get install libatlas-base-dev -y && sudo apt-get install libjasper-dev -y && sudo apt-get install libqtgui4 -y && sudo apt-get install libqt4-test -y
# pip3 install opencv-contrib-python
#
# At the time of writing, you will need to run the server from the command line using the following
# due to an issue with OpenCV 4.1.1.26
# LD_PRELOAD=/usr/lib/arm-linux-gnueabihf/libatomic.so.1 python3 eye_position_server.py

import math
import random
import time
import socket
import selectors
import types
import pickle
import cv2
import imutils # https://github.com/jrosebr1/imutils/
from picamera.array import PiRGBArray
from picamera import PiCamera
import datetime

# Get my IP address
hostname = socket.gethostname()
host = socket.gethostbyname(hostname)
host = '127.0.0.1' # Uncomment this line for local testing
#host = '' # Listen on all available interfaces

# Use this port (make sure the eye clients are using the same one!)
port = 65432

PUPIL_SMOOTH    = 16    # If > 0, filter input from PUPIL_IN
PUPIL_MIN       = 0.0   # Lower analog range from PUPIL_IN
PUPIL_MAX       = 1.0   # Upper "

startX       = random.uniform(-30.0, 30.0)
n            = math.sqrt(900.0 - startX * startX)
startY       = random.uniform(-n, n)
destX        = startX
destY        = startY
curX         = startX
curY         = startY
moveDuration = random.uniform(0.075, 0.175)
holdDuration = random.uniform(0.1, 1.1)
startTime    = 0.0
isMoving     = False
currentPupilScale  =  0.5
lidWeight    = 0.0

AUTOBLINK       = True  # If True, eye blinks autonomously

timeOfLastBlink = 0.0
timeToNextBlink = 1.0
blinkState      = 0
blinkDuration   = 0.1
blinkStartTime  = 0
blinkState 	    = 0

# These are the settings shared with (written to) the client
shared = {"curX":curX, "curY":curY, "pupil":currentPupilScale, "lid":lidWeight, "blink":blinkState}

sel = selectors.DefaultSelector()

lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((host, port))
lsock.listen()
print("listening on", (host, port))
lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

def accept_wrapper(sock):
	conn, addr = sock.accept()  # Should be ready to read
	print("accepted connection from", addr)
	conn.setblocking(False)
	data = types.SimpleNamespace(addr=addr, inb=b"", outb=b"")
	events = selectors.EVENT_WRITE # | selectors.EVENT_READ
	sel.register(conn, events, data=data)

def service_connection(key, mask, shared):
	sock = key.fileobj
	data = key.data
#	if mask & selectors.EVENT_READ:
#		recv_data = sock.recv(3)  # Should be ready to read
#		data.inb = recv_data
#		if recv_data: # Did we receive any data?
#			print("received", repr(recv_data), "from address", data.addr)
#			if recv_data != b"???": # The client should only ever send "???"
#				print("closing connection to", data.addr)
#				sel.unregister(sock)
#				sock.close()
	if mask & selectors.EVENT_WRITE:
		data.outb = pickle.dumps(shared) # pickle the shared variables
		#print("echoing", len(data.outb), "bytes to", data.addr)
		sent = sock.send(data.outb)  # Should be ready to write

# initialize the camera and grab a reference to the raw camera capture
camera = PiCamera()
camera.resolution = (640, 480)
camera.framerate = 5
rawCapture = PiRGBArray(camera, size=(640, 480))
#camera.start_preview() # only used for testing / alignment
#time.sleep(5)

# allow the camera to warmup, then initialize the average frame
print("[INFO] warming up...")
time.sleep(2.5)
avg = None

try:
	while True:
		
		# Motion Detection
		# capture frames from the camera
		for f in camera.capture_continuous(rawCapture, format="bgr"): #, use_video_port=True):
			# grab the raw NumPy array representing the image and initialize
			# the timestamp and occupied/unoccupied text
			frame = f.array
			#timestamp = datetime.datetime.now()
			text = "No Motion"
			
			# resize the frame, convert it to grayscale, and blur it
			frame = imutils.resize(frame, width=500)
			gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
			gray = cv2.GaussianBlur(gray, (21, 21), 0)
			
			# if the average frame is None, initialize it
			if avg is None:
				print("[INFO] starting background model...")
				avg = gray.copy().astype("float")
				rawCapture.truncate(0)
				continue
				
			# accumulate the weighted average between the current frame and
			# previous frames, then compute the difference between the current
			# frame and running average
			cv2.accumulateWeighted(gray, avg, 0.5)
			frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
			
			# threshold the delta image, dilate the thresholded image to fill
			# in holes, then find contours on thresholded image
			thresh = cv2.threshold(frameDelta, 5, 255,
				cv2.THRESH_BINARY)[1]
			thresh = cv2.dilate(thresh, None, iterations=2)
			cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
				cv2.CHAIN_APPROX_SIMPLE)
			cnts = imutils.grab_contours(cnts)
			
			# loop over the contours
			for c in cnts:
				# if the contour is too small, ignore it
				if cv2.contourArea(c) < 5000:
					continue
					
				# compute the bounding box for the contour, draw it on the frame,
				# and update the text
				(x, y, w, h) = cv2.boundingRect(c)
				cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
				text = "Motion!"
				
			# display the image
			cv2.imshow('Motion Detection', frame)
			key = cv2.waitKey(1) & 0xFF
			# if the `r` key is pressed, refresh the average
			if key == ord("q"):
				avg = None
			
			# truncate rawCapture so we can use it again
			# (avoids "Incorrect buffer length for resolution" errors)
			rawCapture.truncate(0)
		
			now = time.time()
			dt  = now - startTime
			
			if (text == "Motion!"):
				
				# Motion detected to move eyes to center of motion
				# and shrink the pupil
				curX = ((x + (w / 2)) - 320) * 0.093 # scale x to +/-30
				curY = ((y + (h / 2)) - 240) * 0.093 # scale y to +/-30
				currentPupilScale = PUPIL_MIN
				
			else:

				# Autonomous eye position
				if isMoving == True:
					if dt <= moveDuration:
						scale        = (now - startTime) / moveDuration
						# Ease in/out curve: 3*t^2-2*t^3
						scale = 3.0 * scale * scale - 2.0 * scale * scale * scale
						curX         = startX + (destX - startX) * scale
						curY         = startY + (destY - startY) * scale
					else:
						startX       = destX
						startY       = destY
						curX         = destX
						curY         = destY
						holdDuration = random.uniform(0.15, 1.7)
						startTime    = now
						isMoving     = False
				else:
					if dt >= holdDuration:
						destX        = random.uniform(-30.0, 30.0)
						n            = math.sqrt(900.0 - destX * destX)
						destY        = random.uniform(-n, n)
						moveDuration = random.uniform(0.075, 0.175)
						startTime    = now
						isMoving     = True
						
				# Autonomous pupil size
				# Use sin to vary the pupil diameter from 50% to PUPIL_MAX over 10 seconds
				currentPupilScale = ((math.sin(2 * math.pi * (now % 10) / 10) / 4) + 0.5) * PUPIL_MAX

			# Blinking
			if AUTOBLINK and (now - timeOfLastBlink) >= timeToNextBlink:
				timeOfLastBlink = now
				duration        = random.uniform(0.06, 0.12)
				if blinkState != 1:
					blinkState     = 1 # ENBLINK
					blinkStartTime = now
					blinkDuration  = duration
				if (text == "Motion!"):
					timeToNextBlink = random.uniform(4.0, 6.0)
				else:
					timeToNextBlink = duration * 3 + random.uniform(0.0, 4.0)

			if blinkState: # Eye currently winking/blinking?
				# Check if blink time has elapsed...
				if (now - blinkStartTime) >= blinkDuration:
					# Increment blink state
					blinkState += 1
					if blinkState > 2:
							blinkState = 0 # NOBLINK
					else:
							blinkDuration *= 2.0
							blinkStartTime = now

			if blinkState:
				lidWeight = (now - blinkStartTime) / blinkDuration
				if lidWeight > 1.0: lidWeight = 1.0
				if blinkState == 2: lidWeight = 1.0 - lidWeight
			else:
				lidWeight = 0.0

			shared = {"curX":curX, "curY":curY, "pupil":currentPupilScale, "lid":lidWeight, "blink":blinkState}
			
			events = sel.select(timeout=None)
			for key, mask in events:
				if key.data is None:
					accept_wrapper(key.fileobj)
				else:
					service_connection(key, mask, shared)


except KeyboardInterrupt:
    print("caught keyboard interrupt, exiting")
    
finally:
	cv2.destroyAllWindows()
	sel.close()
