""" 
Python Class to Create a steeing Wheel from
a Game controller and a Bicycle on a Turbo Trainer
Specifically for playing Test Drive 2 Unlimited

It's quite specific for what I want in terms of devices
mapping and behaviour - not as a generic class

"""


__author__ = "John Page"
__copyright__ = "Copyright 2020 John Page <johnlpage@gmail.com>"
__license__ = "GPLv3-or-later"
__email__ = "johnlpage@gmail.com"
__version__ = "0.0.1"


import smbus
import time
import hid
import py_qmc5883l
import ps3bike.controlmapbits as cmb 
import logging



#TODO - Make These Arguments
#GAMEPAD
GAMEPAD_VID = 0x11C0
GAMEPAD_DID = 0x5503

#A small slide clicker with 4 buttons
#For Brakes etc.
CLICKER_VID=0x1d57
CLICKER_DID=0xad03

GAMEPAD_DATA_LEN = 27 #Ony first 8 matter to me
STEERING_SENSITIVITY = 4

DUTY_CYCLE=20
#One easyt to change paramater to regulate speed
DIFFICULTY = 2

LIGHTSENSOR_DEVICE = 0x23  # Default device I2C address
# Start measurement at 4lx resolution. Time typically 16ms.
LIGHTSENSOR_CONTINUOUS_LOW_RES_MODE = 0x13

POWER_DOWN = 0x00  # No active state
POWER_ON = 0x01  # Power on
RESET = 0x07  # Reset data register value



class PS3Bike(object):
    

    def __init__(self):

        logging.basicConfig(level=logging.DEBUG)

        #Used to maintain the average lux
        self.luxsum = 0
        self.luxcount = 0
        self.luxmean = 0
        self.debounce = False
        self.lastturn = time.time()
        self.turnbuffer = []
        self.speedmean = 0
        self.old_clicker_data = None

        self.gamepad = hid.device()
        self.braking = False
        self.clicker  = hid.device()
        try:
            self.gamepad.open(GAMEPAD_VID, GAMEPAD_DID)
            self.gamepad.set_nonblocking(1)
            self.gamepad_data = bytes(GAMEPAD_DATA_LEN)

            self.clicker.open(CLICKER_VID, CLICKER_DID)
            self.clicker.set_nonblocking(1)
            
        except Exception as e:
             raise Exception("""Unable to open real game controller or clicker - are they
                plugged in and do the VID and DID match?\n""" + str(e))

        try:
            self.emulated_controller_fd = open('/dev/hidg0', 'rb+',buffering=0)
        except Exception as e:
            raise Exception("""Unable to open virtual Joystick - have you created it
                and is this running with permissions to write to it?""" + str(e))

        self.compass = None
        self.forwards = None

        self._enable_sensors();

    def __del__(self):
        pass

    def _read_lightsensor(self):
        data = self.bus.read_i2c_block_data(LIGHTSENSOR_DEVICE, LIGHTSENSOR_CONTINUOUS_LOW_RES_MODE)
        result = (data[1] + (256 * data[0])) / 1.2
        self.luxsum = self.luxsum + result
        self.luxcount += 1
        self.luxmean = self.luxsum / self.luxcount
        return result

    def _read_compass(self):
        #Returns -179 - 179
        if self.compass:
            bearing= self.compass.get_bearing();
            if bearing > 180:
                bearing = bearing - 360
            return bearing
        else:
            return None

    def _calibrate_forwards(self):
        if self.compass:
            while self.forwards == None:
                logging.info("Calibrating Compass")
                self.forwards = self._read_compass();
                if self.forwards == None:
                    time.sleep(0.5)
            logging.info(f"Bike is facing {self.forwards}")

    def _enable_sensors(self):

        try:
            logging.info("Opening Compass")
            self.compass = py_qmc5883l.QMC5883L()
            self._calibrate_forwards()
        except Exception as e:
            raise Exception("Error opening compass, no steering: " + str(e))
        try:
            self.bus = smbus.SMBus(1)  # Rev 2 Pi uses 1
            lightreading = self._read_lightsensor()
            logging.info(f"Lightsensor reads {lightreading}")
        except Exception as e:
            raise Exception("Error opening light sensor, no pedals: " + str(e))  

    

    def _set_steering(self,angle):

        tmp = 128 + (angle*STEERING_SENSITIVITY)
        if tmp > 255:
            tmp=255
        if tmp < 0: 
            tmp=0

        self.gamepad_data[cmb.GAMEPAD_LJOY_X]=int(tmp)
     


    def _send_data(self):
        self.emulated_controller_fd.write(self.gamepad_data)


    def _beam_broken(self):
        if self.debounce or self.braking:
            return #We are in the dark part still
        
        self.debounce = True
        now_time = time.time()
        turntime = now_time - self.lastturn
        if turntime < 2:
            #Wheel is actually turning
            rpm = 60 / turntime
            self.turnbuffer = [rpm] + self.turnbuffer[0:9]
            self.speedmean = sum(self.turnbuffer)/len(self.turnbuffer) * 5 / 60
        else:
            self.turnbuffer = []
            self.speedmean = 0

        #logging.info(f"Average Speed = {self.speedmean}")
        self.lastturn = now_time


    def _into_first_gear(self):
        #Shift to First
        c = cmb.GAMEPAD_CIRCLE
        t = cmb.GAMEPAD_TRIANGLE
        buttons = [c,c,c,c,t,t]
        for button in buttons:
            self.gamepad_data[button[0]] |= button[1]
            self._send_data()
            time.sleep(0.1)
            self.gamepad_data[button[0]] &= ~button[1]
            self._send_data()
            time.sleep(0.1)
   
    def _return_to_road(self):
        #Hold Circle
        self.gamepad_data[cmb.GAMEPAD_CIRCLE[0]] |= cmb.GAMEPAD_CIRCLE[1]
        self._send_data()
        time.sleep(1)

  
    def _brake(self):
        self.turnbuffer = []
        self.speedmean = 0
        self.braking = True

    def _parse_clicker_data(self,clicker_data):
         
        if clicker_data :
            self.braking = False
            byte = clicker_data[cmb.CLICKER_BUTTONS]
            if byte in cmb.CLICKER_UP:
                return self._into_first_gear()
            if byte in cmb.CLICKER_DOWN:
                return self._return_to_road()   
            if byte in cmb.CLICKER_RIGHT:
                return self._brake()   
            if byte in cmb.CLICKER_LEFT:
                exit(0)           
            
        
    def start_controller(self):
        start_time = time.time()
        loops = 0
        loopssinceclick=0

        while True:
            loops += 1
            loopssinceclick += 1
            now_time = time.time()
            hz = loops / (now_time-start_time)
            #logging.info(f"Loop Speed { int(hz)} Hz")
            latest_gamepad_data = bytearray(self.gamepad.read(GAMEPAD_DATA_LEN))
            logging.info(latest_gamepad_data.hex())
            clicker_data = bytearray(self.clicker.read(64))
            bearing = self._read_compass()
            lightreading = self._read_lightsensor()

            if lightreading < self.luxmean * 0.8:
                self._beam_broken()
            else:
                self.debounce = False

            steering_angle = bearing - self.forwards
            #logging.info(f"Steering angle {steering_angle}")

            if len(latest_gamepad_data) == GAMEPAD_DATA_LEN:
                self.gamepad_data = latest_gamepad_data
                
                #Joystick overrides Bike for steering so use if it's neutral
                if self.gamepad_data[cmb.GAMEPAD_LJOY_X] == 0x80:
                    self._set_steering(steering_angle)

                #Click R2 depending on our speed and loop frequency
                #This is basically a duty cycle thing 
                if loops % DUTY_CYCLE < (self.speedmean / DIFFICULTY) :
                        self.gamepad_data[cmb.GAMEPAD_R2[0]] |=  cmb.GAMEPAD_R2[1]

                #Modify whatever the controler got override pedals

                self._parse_clicker_data(clicker_data)

                if self.braking:
                    self.gamepad_data[cmb.GAMEPAD_L2[0]] |= cmb.GAMEPAD_L2[1]
                    self.gamepad_data[cmb.GAMEPAD_R2[0]] &= ~cmb.GAMEPAD_R2[1]
                    logging.info("Braking")
                #logging.info(self.gamepad_data.hex())
                self._send_data()
            else:
                logging.info("No Data from device")


