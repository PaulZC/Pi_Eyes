# Pi_Eyes : Installation Guide

This guide is a summary of how to use a _single_ Raspberry Pi 4 to test the Pi_Eyes code.
The server and clients communicate over local port ```127.0.0.1```

- Download the [Raspberry Pi Imager](https://www.raspberrypi.org/downloads/)
- Choose Raspberry Pi OS **Full** from the Raspberry Pi OS **Other** menu
- Select your SD card and click _Write_
- Go make a cup of tea...
- Remove the SD card and install it in your RPi
- Power up the Pi with a screen, keyboard, mouse and RPi camera attached
- The Pi will resize the SD card and then will start to boot
- Go through the _set up_ process and connect to your network
- You are using a fresh install so you can skip the _Update Software_ option
- Restart the Pi
- Click on the Raspberry logo in the top left corner of the screen and select ```Preferences\Raspberry Pi Configuration```
- Click on the Interfaces tab and Enable the Camera option
  - You may find it useful to enable SSH and VNC too so you can log in remotely using VNC
- Reboot
- Test the camera:
  - Open a console window by clicking on the **>_** icon at the top of the screen
  - Type ```raspistill -t 5000``` and press enter
  - The camera image should appear. Focus the camera if necessary.
- Download and install Pi_Eyes using:
```
cd ~
curl https://raw.githubusercontent.com/PaulZC/Pi_Eyes/master/installer.sh >installer.sh
sudo bash installer.sh
```
- The installer script will ask if you want to continue. Answer **Y**
- Choose option **1** to install the left eye client
  - The script downloads both eye clients and the server too but only the left eye gets added to /etc/rc.local and run at boot
- Choose **Y** to continue
- The installer will install all of the files needed to run the code:
  - **python3-pip python3-dev python3-pil libatlas-base-dev libhdf5-dev libhdf5-serial-dev libjasper-dev libqtgui4 libqt4-test**
  - **numpy pi3d==2.34 svg.path rpi-gpio opencv-contrib-python imutils**
- Go make more tea...
- Reboot with **Y**
- If any of the packages failed to install first time (if you saw any red text during the install) you can repeat the process:
  - Open a console window and type ```sudo bash installer.sh``` to run the installer again
  - You may need to do this more than once...! Keep trying until you see no red text.
  - A successful install ends with:
  ```
  inflating: Pi_Eyes-master/installer.sh
  Configuring system...
  Done.
  ```
- The code is installed into ```/boot/Pi_Eyes```
- For test purposes, it is a good idea to stop the code from running on boot. Open a console and type:
```
sudo nano /etc/rc.local
```
  - Scroll down using the arrow keys and comment out the line at the end of the file using a hash (e.g.) **#cd /boot/Pi_Eyes;LD_PRELOAD=/usr/lib/arm-linux-gnueabihf/libatomic.so.1 python3 eye_position_server.py &**
  - Delete any duplicate copies of that line (if you had to run the installer more than once)
  - Press **Ctrl-X** then **Y** then **Enter**
- Reboot using ```sudo reboot```
- Open three console windows. In all three type ```cd /boot/Pi_Eyes```
- In the first, type ```LD_PRELOAD=/usr/lib/arm-linux-gnueabihf/libatomic.so.1 python3 eye_position_server.py``` to start the server
- In the second, type ```python3 eye_left_client.py```
  - The left eye should appear in a window and start to move. The server window will start displaying camera images and highlight movement with a green box
- In the third, type ```python3 eye_right_client.py```
  - The right eye should appear and start to move too. The two eyes should track together
- Try getting the server to follow your finger with a green box. The eyes should follow...!

Enjoy!

_**Paul**_
