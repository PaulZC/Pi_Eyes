#!/usr/bin/python

# Network crazy eyes : Client
#
# A remix of:
#
# Adafruit / Phillip Burgess (Paint Your Dragon)'s Animated Snake Eyes for Raspberry Pi
# https://learn.adafruit.com/animated-snake-eyes-bonnet-for-raspberry-pi/software-installation
# https://github.com/adafruit/Pi_Eyes
#
# Nathan Jennings / Real Python guide to Socket Programming in Python (Guide)
# https://realpython.com/python-sockets/#handling-multiple-connections
# https://github.com/realpython/materials/blob/master/python-sockets-tutorial/multiconn-client.py

# This renders a single left eye (centered on screen) and
# assumes you are using HDMI for display.

import pickle
import math
import pi3d
import random
import threading
import time
from svg.path import Path, parse_path
from xml.dom.minidom import parse
from gfxutil import *
import sys
import socket
import selectors
import types

# Get my IP address
hostname = socket.gethostname()
host = socket.gethostbyname(hostname)
host = '127.0.0.1' # Uncomment this line for local testing
#host = '' # Listen on all available interfaces

# Use this port (make sure the eye server is using the same one!)
port = 65432

# Set up display and initialize pi3d ---------------------------------------

#DISPLAY = pi3d.Display.create(samples=4, w=640, h=480)
DISPLAY = pi3d.Display.create(samples=4, w=1280, h=720)
#DISPLAY = pi3d.Display.create(samples=4, w=1920, h=1080)
#DISPLAY = pi3d.Display.create(samples=4)
DISPLAY.set_background(0, 0, 0, 1) # r,g,b,alpha

# Load SVG file, extract paths & convert to point lists --------------------

dom               = parse("graphics/eye.svg")
vb                = get_view_box(dom)
pupilMinPts       = get_points(dom, "pupilMin"      , 32, True , True )
pupilMaxPts       = get_points(dom, "pupilMax"      , 32, True , True )
irisPts           = get_points(dom, "iris"          , 32, True , True )
scleraFrontPts    = get_points(dom, "scleraFront"   ,  0, False, False)
scleraBackPts     = get_points(dom, "scleraBack"    ,  0, False, False)
upperLidClosedPts = get_points(dom, "upperLidClosed", 33, False, True )
upperLidOpenPts   = get_points(dom, "upperLidOpen"  , 33, False, True )
upperLidEdgePts   = get_points(dom, "upperLidEdge"  , 33, False, False)
lowerLidClosedPts = get_points(dom, "lowerLidClosed", 33, False, False)
lowerLidOpenPts   = get_points(dom, "lowerLidOpen"  , 33, False, False)
lowerLidEdgePts   = get_points(dom, "lowerLidEdge"  , 33, False, False)

TRACKING        = True  # If True, eyelid tracks pupil

# eyeRadius is the size, in pixels, at which the whole eye will be rendered.
if DISPLAY.width <= (DISPLAY.height * 2):
	# For WorldEye, eye size is -almost- full screen height
	eyeRadius   = DISPLAY.height / 2.1
else:
	eyeRadius   = DISPLAY.height * 2 / 5

# A 2D camera is used, mostly to allow for pixel-accurate eye placement,
# but also because perspective isn't really helpful or needed here, and
# also this allows eyelids to be handled somewhat easily as 2D planes.
# Line of sight is down Z axis, allowing conventional X/Y cartesion
# coords for 2D positions.
cam    = pi3d.Camera(is_3d=False, at=(0,0,0), eye=(0,0,-1000))
shader = pi3d.Shader("uv_light")
light  = pi3d.Light(lightpos=(0, -500, -500), lightamb=(0.2, 0.2, 0.2))


# Load texture maps --------------------------------------------------------

irisMap   = pi3d.Texture("graphics/iris.jpg"  , mipmap=False,
              filter=pi3d.GL_LINEAR)
scleraMap = pi3d.Texture("graphics/sclera.png", mipmap=False,
              filter=pi3d.GL_LINEAR, blend=True)
lidMap    = pi3d.Texture("graphics/lid.png"   , mipmap=False,
              filter=pi3d.GL_LINEAR, blend=True)
# U/V map may be useful for debugging texture placement; not normally used
#uvMap     = pi3d.Texture("graphics/uv.png"    , mipmap=False,
#              filter=pi3d.GL_LINEAR, blend=False, m_repeat=True)


# Initialize static geometry -----------------------------------------------

# Transform point lists to eye dimensions
scale_points(pupilMinPts      , vb, eyeRadius)
scale_points(pupilMaxPts      , vb, eyeRadius)
scale_points(irisPts          , vb, eyeRadius)
scale_points(scleraFrontPts   , vb, eyeRadius)
scale_points(scleraBackPts    , vb, eyeRadius)
scale_points(upperLidClosedPts, vb, eyeRadius)
scale_points(upperLidOpenPts  , vb, eyeRadius)
scale_points(upperLidEdgePts  , vb, eyeRadius)
scale_points(lowerLidClosedPts, vb, eyeRadius)
scale_points(lowerLidOpenPts  , vb, eyeRadius)
scale_points(lowerLidEdgePts  , vb, eyeRadius)

# Regenerating flexible object geometry (such as eyelids during blinks, or
# iris during pupil dilation) is CPU intensive, can noticably slow things
# down, especially on single-core boards.  To reduce this load somewhat,
# determine a size change threshold below which regeneration will not occur;
# roughly equal to 1/2 pixel, since 2x2 area sampling is used.

# Determine change in pupil size to trigger iris geometry regen
irisRegenThreshold = 0.0
a = points_bounds(pupilMinPts) # Bounds of pupil at min size (in pixels)
b = points_bounds(pupilMaxPts) # " at max size
maxDist = max(abs(a[0] - b[0]), abs(a[1] - b[1]), # Determine distance of max
              abs(a[2] - b[2]), abs(a[3] - b[3])) # variance around each edge
# maxDist is motion range in pixels as pupil scales between 0.0 and 1.0.
# 1.0 / maxDist is one pixel's worth of scale range.  Need 1/2 that...
if maxDist > 0: irisRegenThreshold = 0.5 / maxDist

# Determine change in eyelid values needed to trigger geometry regen.
# This is done a little differently than the pupils...instead of bounds,
# the distance between the middle points of the open and closed eyelid
# paths is evaluated, then similar 1/2 pixel threshold is determined.
upperLidRegenThreshold = 0.0
lowerLidRegenThreshold = 0.0
p1 = upperLidOpenPts[len(upperLidOpenPts) // 2]
p2 = upperLidClosedPts[len(upperLidClosedPts) // 2]
dx = p2[0] - p1[0]
dy = p2[1] - p1[1]
d  = dx * dx + dy * dy
if d > 0: upperLidRegenThreshold = 0.5 / math.sqrt(d)
p1 = lowerLidOpenPts[len(lowerLidOpenPts) // 2]
p2 = lowerLidClosedPts[len(lowerLidClosedPts) // 2]
dx = p2[0] - p1[0]
dy = p2[1] - p1[1]
d  = dx * dx + dy * dy
if d > 0: lowerLidRegenThreshold = 0.5 / math.sqrt(d)

# Generate initial iris mesh; vertex elements will get replaced on
# a per-frame basis in the main loop, this just sets up textures, etc.
iris = mesh_init((32, 4), (0.5, 0.5 / irisMap.iy), True, False) ## RIGHT IS 0.0, 0.5
iris.set_textures([irisMap])
iris.set_shader(shader)
irisZ = zangle(irisPts, eyeRadius)[0] * 0.99 # Get iris Z depth, for later

# Eyelid meshes are likewise temporary; texture coordinates are
# assigned here but geometry is dynamically regenerated in main loop.
upperEyelid = mesh_init((33, 5), (0, 0.5 / lidMap.iy), False, True)
upperEyelid.set_textures([lidMap])
upperEyelid.set_shader(shader)
lowerEyelid = mesh_init((33, 5), (0, 0.5 / lidMap.iy), False, True)
lowerEyelid.set_textures([lidMap])
lowerEyelid.set_shader(shader)

# Generate sclera for eye...start with a 2D shape for lathing...
angle1 = zangle(scleraFrontPts, eyeRadius)[1] # Sclera front angle
angle2 = zangle(scleraBackPts , eyeRadius)[1] # " back angle
aRange = 180 - angle1 - angle2
pts    = []
for i in range(24):
	ca, sa = pi3d.Utility.from_polar((90 - angle1) - aRange * i / 23)
	pts.append((ca * eyeRadius, sa * eyeRadius))

eye = pi3d.Lathe(path=pts, sides=64)
eye.set_textures([scleraMap])
eye.set_shader(shader)
re_axis(eye, 0.5) ## RIGHT IS 0.0


# Init global stuff --------------------------------------------------------

#mykeys = pi3d.Keyboard() # For capturing key presses

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

frames        = 0
beginningTime = time.time()

eye.positionX(0.0)
iris.positionX(0.0)
upperEyelid.positionX(0.0)
upperEyelid.positionZ(-eyeRadius - 42)
lowerEyelid.positionX(0.0)
lowerEyelid.positionZ(-eyeRadius - 42)

lidWeight    = 0.0
blinkState      = 0

currentPupilScale  =  0.5
prevPupilScale     = -1.0 # Force regen on first frame
prevUpperLidWeight = 0.5
prevLowerLidWeight = 0.5
prevUpperLidPts    = points_interp(upperLidOpenPts, upperLidClosedPts, 0.5)
prevLowerLidPts    = points_interp(lowerLidOpenPts, lowerLidClosedPts, 0.5)

ruRegen = True
rlRegen = True

trackingPos = 0.3

# These are the settings shared by (read from) the server
shared = {"curX":curX, "curY":curY, "pupil":currentPupilScale, "lid":lidWeight, "blink":blinkState}

# Generate one frame of imagery
def frame():

	global startX, startY, destX, destY, curX, curY
	global moveDuration, holdDuration, startTime, isMoving
	global frames
	global iris
	global pupilMinPts, pupilMaxPts, irisPts, irisZ
	global eye
	global upperEyelid, lowerEyelid
	global upperLidOpenPts, upperLidClosedPts, lowerLidOpenPts, lowerLidClosedPts
	global upperLidEdgePts, lowerLidEdgePts
	global prevUpperLidPts, prevLowerLidPts
	global prevUpperLidWeight, prevLowerLidWeight
	global prevPupilScale
	global irisRegenThreshold, upperLidRegenThreshold, lowerLidRegenThreshold
	global luRegen, llRegen, ruRegen, rlRegen
	global timeOfLastBlink, timeToNextBlink
	global blinkState
	global blinkDuration
	global blinkStartTime
	global trackingPos
	global shared

	DISPLAY.loop_running()

	now = time.time()
	dt  = now - startTime

	frames += 1

	curX = shared["curX"]
	curY = shared["curY"]
	p = shared["pupil"]
	lidWeight = shared["lid"]
	blinkState = shared["blink"]

	# Regenerate iris geometry only if size changed by >= 1/2 pixel
	if abs(p - prevPupilScale) >= irisRegenThreshold:
		# Interpolate points between min and max pupil sizes
		interPupil = points_interp(pupilMinPts, pupilMaxPts, p)
		# Generate mesh between interpolated pupil and iris bounds
		mesh = points_mesh((None, interPupil, irisPts), 4, -irisZ, True)
		iris.re_init(pts=mesh)
		prevPupilScale = p

	# Eyelid WIP

	if TRACKING:
		# 0 = fully up, 1 = fully down
		n = 0.4 - curY / 60.0
		if   n < 0.0: n = 0.0
		elif n > 1.0: n = 1.0
		trackingPos = (trackingPos * 3.0 + n) * 0.25


	newUpperLidWeight = trackingPos + (lidWeight * (1.0 - trackingPos))
	newLowerLidWeight = (1.0 - trackingPos) + (lidWeight * trackingPos)

	if (ruRegen or (abs(newUpperLidWeight - prevUpperLidWeight) >=
	  upperLidRegenThreshold)):
		newUpperLidPts = points_interp(upperLidOpenPts,
		  upperLidClosedPts, newUpperLidWeight)
		if newUpperLidWeight > prevUpperLidWeight:
			upperEyelid.re_init(pts=points_mesh(
			  (upperLidEdgePts, prevUpperLidPts,
			  newUpperLidPts), 5, 0, False))
		else:
			upperEyelid.re_init(pts=points_mesh(
			  (upperLidEdgePts, newUpperLidPts,
			  prevUpperLidPts), 5, 0, False))
		prevUpperLidWeight = newUpperLidWeight
		prevUpperLidPts    = newUpperLidPts
		ruRegen = True
	else:
		ruRegen = False

	if (rlRegen or (abs(newLowerLidWeight - prevLowerLidWeight) >=
	  lowerLidRegenThreshold)):
		newLowerLidPts = points_interp(lowerLidOpenPts,
		  lowerLidClosedPts, newLowerLidWeight)
		if newLowerLidWeight > prevLowerLidWeight:
			lowerEyelid.re_init(pts=points_mesh(
			  (lowerLidEdgePts, prevLowerLidPts,
			  newLowerLidPts), 5, 0, True)) ## RIGHT IS False
		else:
			lowerEyelid.re_init(pts=points_mesh(
			  (lowerLidEdgePts, newLowerLidPts,
			  prevLowerLidPts), 5, 0, True)) ## RIGHT IS False
		prevLowerLidWeight = newLowerLidWeight
		prevLowerLidPts    = newLowerLidPts
		rlRegen = True
	else:
		rlRegen = False
		
	convergence = 2.0

	# Draw eye

	iris.rotateToX(curY)
	iris.rotateToY(curX+convergence) ## RIGHT IS -
	iris.draw()
	eye.rotateToX(curY)
	eye.rotateToY(curX+convergence) ## RIGHT IS -
	eye.draw()
	upperEyelid.draw()
	lowerEyelid.draw()


sel = selectors.DefaultSelector()

def start_connections(host, port):                        
        print("Searching for server")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.settimeout(0.01)
        ip_LSB = 0
        successful = False
        while (successful == False):
                try:
                        net = host.split('.')
                        try_ip = net[0] + '.' + net[1] + '.' + net[2] + '.' + str(ip_LSB)
                        print("Trying:", try_ip)
                        server_addr = (try_ip, port)
                        if (sock.connect_ex(server_addr) == 0):
                                successful = True
                        else:
                                ip_LSB = ip_LSB + 1
                except:
                        ip_LSB = ip_LSB + 1
                if (ip_LSB == 256):
                        print("Could not find server. Exiting...")
                        sel.close()
                        exit(0)                        
        print("Connected!")
        events = selectors.EVENT_READ # | selectors.EVENT_WRITE
        data = types.SimpleNamespace(
                inb=b"",
                outb=b"",
        )
        sel.register(sock, events, data=data)

def service_connection(key, mask):
        global shared

        sock = key.fileobj
        data = key.data
        if mask & selectors.EVENT_READ:
                recv_data = sock.recv(102)  # Should be ready to read
                if recv_data:
                        #print("Received", len(recv_data), "bytes")
                        data.inb = recv_data
                        try:
                                shared = pickle.loads(recv_data)
                        except:
                                print("pickle.loads failed. Closing connection.")
                                sel.unregister(sock)
                                sock.close()
                else:
                        pass # We got no data. We should probably do something about this?
#        if mask & selectors.EVENT_WRITE:
#                pass
#                data.outb = b"???"
#                print("sending", repr(data.outb))
#                sent = sock.send(data.outb)  # Should be ready to write

start_connections(host, int(port))

# MAIN LOOP -- runs continuously -------------------------------------------

try:
        while True:
                frame()
                
                events = sel.select(timeout=0.01)
                if events:
                        for key, mask in events:
                                service_connection(key, mask)
                # Check for a socket being monitored to continue.
                if not sel.get_map():
                        break
                
except KeyboardInterrupt:
        print("caught keyboard interrupt, exiting")
    
finally:
        DISPLAY.stop()
        sel.close()
