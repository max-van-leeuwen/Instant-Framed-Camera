# Instant Framed Camera
The code used for both the camera and the frame in my 'Instant Framed Camera' project.
[More on this project here!](https://maxvanleeuwen.com/project/instant-framed-camera/)
The scripts auto-start using a cron job, and [some fast-bootup tricks were applied](http://himeshp.blogspot.com/2018/08/fast-boot-with-raspberry-pi.html).

<br/><br/><br/>

# Hardware used

Camera
- Original Polaroid land camera
- Raspberry Pi 3 Model A+
- [Raspberry Camera Module 3](https://www.raspberrypi.com/products/camera-module-3/)
- [Li-ion Battery HAT](https://www.waveshare.com/li-ion-battery-hat.htm)
- A status LED (pin 18, BCM)
- The camera's original push button was repurposed using GPIO pins (21) to connect when pushed to take the digital picture

Display
- A nice looking photo frame 🖼️ (big thanks to my good friend Liisi)
- Raspberry Pi 3 Model A+
- [5.65inch ACeP 7-Color E-Paper E-Ink Display Module (600x448)](https://www.waveshare.com/5.65inch-e-paper-module-f.htm)
- I added a push button (pin 16, BCM) to reset the display, but it's not really necessary

<br/><br/><br/>

# Software requirements

Python3

Camera
- pyzbar
- opencv-python
- numpy

Display
- The Waveshare libs that come with the e-paper display
- RPi.GPIO
- spidev
- Jetson.GPIO