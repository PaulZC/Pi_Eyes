#!/bin/bash

if [ $(id -u) -ne 0 ]; then
	echo "Installer must be run as root."
	echo "Try 'sudo bash $0'"
	exit 1
fi

clear

echo "This script installs software for the Adafruit"
echo "Pi Eyes for Raspberry Pi (PaulZC Remix)."
echo "Steps include:"
echo "- Update package index files (apt-get update)"
echo "- Install Python libraries: numpy, pi3d, svg.path,"
echo "  rpi-gpio, python3-dev, python3-pil, imutils"
echo "  OpenCV: libhdf5-dev libhdf5-serial-dev"
echo "  libatlas-base-dev libjasper-dev libqtgui4 libqt4-test"
echo "- Install Adafruit eye code and data in /boot"
echo "Reboot required."
echo "EXISTING INSTALLATION, IF ANY, WILL BE OVERWRITTEN."
echo
echo -n "CONTINUE? [y/N] "
read
if [[ ! "$REPLY" =~ ^(yes|y|Y)$ ]]; then
	echo "Canceled."
	exit 0
fi

# FEATURE PROMPTS ----------------------------------------------------------
# Installation doesn't begin until after all user input is taken.

# Given a list of strings representing options, display each option
# preceded by a number (1 to N), display a prompt, check input until
# a valid number within the selection range is entered.
selectN() {
	for ((i=1; i<=$#; i++)); do
		echo $i. ${!i}
	done
	echo
	REPLY=""
	while :
	do
		echo -n "SELECT 1-$#: "
		read
		if [[ $REPLY -ge 1 ]] && [[ $REPLY -le $# ]]; then
			return $REPLY
		fi
	done
}

CODE_NAMES=("LEFT EYE" "RIGHT EYE" "EYE SERVER")
echo
echo "Select which code to run on boot:"
selectN "${CODE_NAMES[0]}" \
        "${CODE_NAMES[1]}" \
        "${CODE_NAMES[2]}"
CODE_SELECT=$?

echo
echo -n "CONTINUE? [y/N] "
read
if [[ ! "$REPLY" =~ ^(yes|y|Y)$ ]]; then
	echo "Canceled."
	exit 0
fi

# START INSTALL ------------------------------------------------------------
# All selections are validated at this point...

# Given a filename, a regex pattern to match and a replacement string,
# perform replacement if found, else append replacement to end of file.
# (# $1 = filename, $2 = pattern to match, $3 = replacement)
reconfig() {
	grep $2 $1 >/dev/null
	if [ $? -eq 0 ]; then
		# Pattern found; replace in file
		sed -i "s/$2/$3/g" $1 >/dev/null
	else
		# Not found; append (silently)
		echo $3 | sudo tee -a $1 >/dev/null
	fi
}

# Same as above, but appends to same line rather than new line
reconfig2() {
	grep $2 $1 >/dev/null
	if [ $? -eq 0 ]; then
		# Pattern found; replace in file
		sed -i "s/$2/$3/g" $1 >/dev/null
	else
		# Not found; append to line (silently)
                sed -i "s/$/ $3/g" $1 >/dev/null
	fi
}

echo
echo "Starting installation..."
echo "Updating package index files..."
apt-get update

echo "Installing Python libraries..."
# WAS: apt-get install -y python3-pip python3-dev python3-pil python3-smbus libatlas-base-dev
apt-get install -y python3-pip python3-dev python3-pil libatlas-base-dev libhdf5-dev libhdf5-serial-dev libjasper-dev libqtgui4 libqt4-test
# WAS: pip3 install numpy pi3d==2.34 svg.path rpi-gpio adafruit-blinka adafruit-circuitpython-ads1x15
pip3 install numpy pi3d==2.34 svg.path rpi-gpio opencv-contrib-python imutils

echo "Installing Adafruit code and data in /boot..."
cd /tmp
curl -LO https://github.com/PaulZC/Pi_Eyes/archive/Pi_Eyes.zip
unzip Pi_Eyes.zip
# Moving between filesystems requires copy-and-delete:
cp -r Pi_Eyes /boot/Pi_Eyes
rm -rf master.zip Pi_Eyes

# CONFIG -------------------------------------------------------------------

echo "Configuring system..."

# Disable overscan compensation (use full screen):
raspi-config nonint do_overscan 1

## If rendering is slow at 1920x1080, uncomment the next four lines to default to 1280x720
## You will need to change the display size in the eye clients to match
#reconfig /boot/config.txt "^.*hdmi_force_hotplug.*$" "hdmi_force_hotplug=1"
#reconfig /boot/config.txt "^.*hdmi_group.*$" "hdmi_group=2"
#reconfig /boot/config.txt "^.*hdmi_mode.*$" "hdmi_mode=87"
#reconfig /boot/config.txt "^.*hdmi_cvt.*$" "hdmi_cvt=1280 720 60 1 0 0 0"

# Install eye_left_client.py, eye_right_client.py or eye_position_server.py
if [ $CODE_SELECT -eq 1 ]; then
	# Auto-start eye_left_client.py on boot
	grep eye_left_client.py /etc/rc.local >/dev/null
	if [ $? -eq 0 ]; then
		# eye_left_client.py already in rc.local, but make sure correct:
		sed -i "s/^.*eye_left_client.py.*$/cd \/boot\/Pi_Eyes;python3 eye_left_client.py \&/g" /etc/rc.local >/dev/null
	else
		# Insert eye_left_client.py into rc.local before final 'exit 0'
	sed -i "s/^exit 0/cd \/boot\/Pi_Eyes;python3 eye_left_client.py \&\\nexit 0/g" /etc/rc.local >/dev/null
	fi
elif [ $CODE_SELECT -eq 2 ]; then
	# Auto-start eye_right_client.py on boot
	grep eye_right_client.py /etc/rc.local >/dev/null
	if [ $? -eq 0 ]; then
		# eye_right_client.py already in rc.local, but make sure correct:
		sed -i "s/^.*eye_right_client.py.*$/cd \/boot\/Pi_Eyes;python3 eye_right_client.py \&/g" /etc/rc.local >/dev/null
	else
		# Insert eye_right_client.py into rc.local before final 'exit 0'
	sed -i "s/^exit 0/cd \/boot\/Pi_Eyes;python3 eye_right_client.py \&\\nexit 0/g" /etc/rc.local >/dev/null
	fi
else
	# Auto-start eye_position_server.py on boot
	grep eye_right_client.py /etc/rc.local >/dev/null
	if [ $? -eq 0 ]; then
		# eye_position_server.py already in rc.local, but make sure correct:
		sed -i "s/^.*eye_position_server.py.*$/cd \/boot\/Pi_Eyes;python3 eye_position_server.py \&/g" /etc/rc.local >/dev/null
	else
		# Insert eye_position_server.py into rc.local before final 'exit 0'
        # Temporary (?) fix for OpenCV
        #sed -i "s/^exit 0/cd \/boot\/Pi_Eyes;python3 eye_position_server.py \&\\nexit 0/g" /etc/rc.local >/dev/null
	sed -i "s/^exit 0/cd \/boot\/Pi_Eyes;LD_PRELOAD=/usr/lib/arm-linux-gnueabihf/libatomic.so.1 python3 eye_position_server.py \&\\nexit 0/g" /etc/rc.local >/dev/null
	fi
fi

# PROMPT FOR REBOOT --------------------------------------------------------

echo "Done."
echo
echo "Settings take effect on next boot."
echo
echo -n "REBOOT NOW? [y/N] "
read
if [[ ! "$REPLY" =~ ^(yes|y|Y)$ ]]; then
	echo "Exiting without reboot."
	exit 0
fi
echo "Reboot started..."
reboot
exit 0
