# Pi_Eyes

This project is a remix of the fantastic:
- [Adafruit / Phillip Burgess (Paint Your Dragon)'s Animated Snake Eyes for Raspberry Pi](https://learn.adafruit.com/animated-snake-eyes-bonnet-for-raspberry-pi/software-installation)
- [Nathan Jennings / Real Python guide to Socket Programming in Python (Guide)](https://realpython.com/python-sockets/#handling-multiple-connections)
- [Adrian Rosebrock's motion detection tutorial](https://www.pyimagesearch.com/2015/06/01/home-surveillance-and-motion-detection-with-the-raspberry-pi-python-and-opencv/)

## You will need:
- Three Raspberry Pi's
- Two HDMI screens which can support 1920x1080 pixels
- A Raspberry Pi camera for the motion detection

The server needs to have the camera interface enabled.

You do not need the Adafruit Snake Eyes Bonnet. This remix only supports HDMI.

## Installation
Run the following script to install the code on each of the three Pi's.
Set one to LEFT EYE, one to RIGHT EYE, and the one with the camera to EYE SERVER
```
cd ~
curl https://raw.githubusercontent.com/PaulZC/Pi_Eyes/master/installer.sh >installer.sh
sudo bash installer.sh
```
The code is installed into ```\boot\Pi_Eyes```

If you want to stop the code running on boot:
```
sudo nano /etc/rc.local
```
and comment out the line at the end of the file (e.g.) **#python3 eye_left_client.py**

## Usage
- Start the eye server first (so the eye clients can find it)
- Then start the two clients

All being well, the eyes should start random movement.
They will track motion when the camera sees it.

Edit the code and change the host IP address to ```127.0.0.1``` for local testing on a single Pi.

Raspberry Pi 4 can just about run both eyes and the server at the same time (but not at 1920x1080).

You can remove the eye window banner by right clicking in the banner and selecting _Un/Decorate_.

## Errata
At the time of writing, you will need to run the server from the command line using the following due to an issue with OpenCV 4.1.1.26
```
LD_PRELOAD=/usr/lib/arm-linux-gnueabihf/libatomic.so.1 python3 eye_position_server.py
```

## Acknowledgements
Raspberry Pi is a trademark of the Raspberry Pi Foundation

Enjoy!

_**Paul**_
