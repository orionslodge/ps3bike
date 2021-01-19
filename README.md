# ps3bike
A Game Controller which is also smart bike trainer.

See https://orionslodge.blogspot.com/

Now tied into PC, Game Telemerty and providing varialbe resitatnce.

I finally got not just controller emulation but the wheel too, hooray.

This code uses a Raspberry Pi 4 to intercept the signal from a wired PS3  controller (copy) to the PS3.
It then modifies that signal based on some i2c sensors ( Light level and Compass) and also
a USB Presentation clicker to allow you to control games, specifically Test Drive 2 Unlimited
with a Bicycle in a Turbo Trainer.

To use as is you will need.

* A Games Console
* A Driving game with a very slow car (U use the Beetle in TDU2)
  * Put the car in manual 1st gear
* A Pi 4 (and USB Type c to A cable)
* A USB powered hub 
* A qmc5883l digital compass
* A i2c light sensor
* A Wired PS Controller
* A presentation clicker with 4 buttons.

And a projector, bike and turbo/stationary trainer


-----------

No
lsusb

Bus 003 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub Bus 001 Device 007: ID 11c0:5503 Betop Bus 001 Device 006: ID 046d:c29a Logitech, Inc. Bus 001 Device 003: ID 1d57:ad03 Xenta Bus 001 Device 002: ID 2109:3431 VIA Labs, Inc. Hub Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub

sudo usbhid-dump

001:007:000:DESCRIPTOR 1605264796.919237 05 01 09 05 A1 01 15 00 25 01 35 00 45 01 75 01 95 0D 05 09 19 01 29 0D 81 02 95 03 81 01 05 01 25 07 46 3B 01 75 04 95 01 65 14 09 39 81 42 65 00 95 01 81 01 26 FF 00 46 FF 00 09 30 09 31 09 32 09 35 75 08 95 04 81 02 06 00 FF 09 20 09 21 09 22 09 23 09 24 09 25 09 26 09 27 09 28 09 29 09 2A 09 2B 95 0C 81 02 0A 21 26 95 08 B1 02 0A 21 26 91 02 26 FF 03 46 FF 03 09 2C 09 2D 09 2E 09 2F 75 10 95 04 81 02 C0

View with

http://eleccelerator.com/usbdescreqparser/#


use hidapi Python module

Observe what each control does with
```
!/usr/bin/python3
import smbus 
import time 
import hid 



-------------

Create Virtual Joystick - convert existing HID Desctiptior
NB Also Make use you change HID Message size to right length - this stuck me for days

https://github.com/milador/RaspberryPi-Joystick

---------------------------
```
echo " 05 01 09 04 A1 01 15 00 25 07 35 00 46 3B 01 65 14 09 39 75 04 95 01 81 42 65 00 25 01 45 01 05 09 19 01 29 15 75 01 95 15 81 02 06 00 FF 09 01 95 07 81 02 26 FF 3F 46 FF 3F 75 0E 95 01 05 01 09 30 81 02 25 01 45 01 06 00 FF 09 01 75 01 95 02 81 02 26 FF 00 46 FF 00 05 01 09 31 09 32 75 08 81 02 95 07 06 00 FF 09 02 91 02 95 83 09 03 B1 02 C0" | sed 's/ //g'
```
With one USB device

```
 sudo usbhid-dump | tail +2 | sed -s 's/ //g' | sed -z 's/\n//g'
```

wheel = hid.device() 
wheel.open(0x046d,0xc29a )

while True:
    wheeldata = bytearray(wheel.read(64)) 
    print(wheeldata.hex())

```
