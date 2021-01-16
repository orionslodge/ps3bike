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
__version__ = "1.1"

import multiprocessing
import smbus
import time
import hid
import py_qmc5883l
import ps3bike.controlmapbits as cmb 
import logging
import ps3bike.webui as webui
import socket 

from struct import *
from pprint import pprint


CREW_TELEMETRY_IP = "0.0.0.0"
CREW_TELEMETRY_PORT = 5005

GAMEPAD_VID = 0x11C0
GAMEPAD_DID = 0x5503

#A small slide clicker with 4 buttons
#For Brakes etc.
CLICKER_VID=0x1d57
CLICKER_DID=0xad03

GAMEPAD_DATA_LEN = 27 
STEERING_SENSITIVITY = 4

LIGHTSENSOR_DEVICE = 0x23  # Default device I2C address
LIGHTSENSOR_CONTINUOUS_LOW_RES_MODE = 0x13

POWER_DOWN = 0x00  # No active state
POWER_ON = 0x01  # Power on
RESET = 0x07  # Reset data register value

DEFAULT_SPEED_CALIBRATION = 9
DEFAULT_SPEED_OFFSET = 40
MEANBUFLEN=2


class PS3Bike(object):
    

    def _apply_acceleration(self,loops,speed_mean):
        #Do not do this in XMB

        pedal_press = speed_mean * self.speed_calibration.value
        if speed_mean > 1:
            pedal_press=pedal_press + self.speed_offset.value

        #If we have a none zero game speed then let's try to calibrate it
        if self.crew_target_speed != None and self.crew_target_speed >= 0: 
            if self.new_telemetry:
                logging.info(f"Mean Speed: {speed_mean} Game Speed: {self.crew_target_speed} {int(self.auto_pedal)}")
                diff = abs(self.crew_target_speed - speed_mean)
                if speed_mean > self.crew_target_speed-3 and speed_mean > 0:
                    self.auto_pedal += 3
                else:
                    self.auto_pedal -= 3

                if self.auto_pedal <0:
                    self.auto_pedal = 0
                if self.auto_pedal > 0x7F:
                    self.auto_pedal = 0x7F

                self.new_telemetry = False
 
            pedal_press = int(self.auto_pedal + 128)


        if pedal_press >  0xFF:
            pedal_pesss = 0xFF
        self.wheel_data[cmb.WHEEL_ACCELERATEBYTE] = pedal_press
        


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
        self.auto_pedal=0
        self.old_clicker_data = None
        self.wheel_data = bytearray(cmb.WHEEL_NEUTRAL)
        self.crew_target_speed = None
        self.gamepad = hid.device()
        self.braking = False
        self.new_telemetry = False
        self.clicker  = hid.device()
        try:
            logging.info("Opening PS Gamepad") 
            self.gamepad.open(GAMEPAD_VID, GAMEPAD_DID)
            #self.gamepad.set_nonblocking(1)
            self.gamepad_data = bytes(GAMEPAD_DATA_LEN)
            logging.info("Opening CLicker")
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


        
        self.speed_calibration = multiprocessing.Value('i')
        self.speed_offset = multiprocessing.Value('i')
        self.speed_calibration.value = DEFAULT_SPEED_CALIBRATION
        self.speed_offset.value = DEFAULT_SPEED_OFFSET

        self.load_settings()
       

        self.compass = None
        self.forwards = None
        try:
            self.crew_telemetry_socket = socket.socket(socket.AF_INET, # Internet
                          socket.SOCK_DGRAM) # UDP
            self.crew_telemetry_socket.setblocking(0)

            self.crew_telemetry_socket.bind((CREW_TELEMETRY_IP, CREW_TELEMETRY_PORT))
            logging.info("Opened The Crew telemetry socket")
        except Exception as e:
            logging.info("CANNOT OPEN The Crew telemetry socket")
            logging.info(e)
            self.crew_telemetry_socket = None
 


        self._enable_sensors();

    def read_crew_telemetry(self):
        if self.crew_telemetry_socket == None:
            return
        try:
          data, addr = self.crew_telemetry_socket.recvfrom(128) # buffer size is 1024 bytes
          #print("received telemetry message: %s" % data)
          fmt = 'IffffffffffffIIII'
          telemetry = unpack(fmt,data)
          telemetry = list(map( lambda x : round(x,2),telemetry))
          b=0
          tobj = {
            'time': telemetry[0],
            'angularVelocity': telemetry[1:4],
            'orientation': telemetry[4:7],
            'acceleration': telemetry[7:10],
            'velocity': telemetry[10:13],
            'position': telemetry[13:16],
            'gameid' : telemetry[16]
          };

          self.crew_target_speed = tobj['velocity'][1] * 2.2
          self.new_telemetry = True
          #pprint(f"Telemetry Speed : {self.crew_target_speed}" )
        except:
          pass

    def __del__(self):
        pass

    def load_settings(self):
        #Try to load settings
        try:
            settingsfile = open("psbike.settings")
            vals = settingsfile.read().split(",")
            self.speed_calibration.value = int(vals[0])
            self.speed_offset.value = int(vals[1])
        except Exception as e:
            logging.info(f"Error loading settings: {str(e)}")

    def save_settings(self):
        logging.info("Saving Settings")
        try:
            settingsfile = open("psbike.settings","w")
            settingsfile.write(f"{self.speed_calibration.value},{self.speed_offset.value}")
            settingsfile.close()
        except Exception as e:
            logging.info(f"Error loading settings: {str(e)}")

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

        self._map_steering(int(tmp))
       
     


    def _send_data(self):
        #logging.info(self.wheel_data.hex())
        self.emulated_controller_fd.write(self.wheel_data)


    def _beam_broken(self):
        now_time = time.time()
        turntime = now_time - self.lastturn

        if self.debounce or self.braking:
            return #We are in the dark part still
        
        self.debounce = True
       

        rpm = 60 / turntime
        self.turnbuffer = [rpm] + self.turnbuffer[0:MEANBUFLEN]
        self.speedmean = sum(self.turnbuffer)/len(self.turnbuffer) * 5 / 60
       

        #logging.info(f"Average Speed = {self.speedmean}")
        self.lastturn = now_time


    def _into_first_gear(self):
        #Shift to First
        c = cmb.WHEEL_GEARDOWN
        t = cmb.WHEEL_GEARUP
        buttons = [c,c,c,c,t,t]
        for button in buttons:
            self.wheel_data[button[0]] |= button[1]
            self._send_data()
            time.sleep(0.2)
            self.wheel_data[button[0]] &= ~button[1]
            self._send_data()
            time.sleep(0.2)
    
   
    def _return_to_road(self):
        #Hold Circle
        self.wheel_data[cmb.WHEEL_CIRCLE[0]] |= cmb.WHEEL_CIRCLE[1]
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
                #Reset the controller
                exit(0)           
            
    def sensor_loop(self,speed_mean,steering_angle):
        start_time = time.time()

        while True:
            now_time = time.time()
            clicker_data = bytearray(self.clicker.read(64))
            try:
                bearing = self._read_compass()
                steering_angle.value = bearing - self.forwards
            except:
                pass

            
            lightreading = self._read_lightsensor()


            if lightreading < self.luxmean * 0.8:
                self._beam_broken()
            else:
                self.debounce = False
                

            speed_mean.value=self.speedmean

            
           
            if self.speedmean > 0:
                self.speedmean = self.speedmean - 0.5

    def _map_pad_to_wheel(self):
      
        for mapping in cmb.DPAD_MAPPINGS:
            if (self.gamepad_data[mapping[0][0]] & cmb.GAMEPAD_DPAD_MASK) ==  mapping[0][1] :
                self.wheel_data[mapping[1][0]] &= ~cmb.WHEEL_DPAD_MASK
                self.wheel_data[mapping[1][0]] |= mapping[1][1]

        mappings = cmb.BUTTON_MAPPINGS

        for mapping in mappings:
            if self.gamepad_data[mapping[0][0]] & mapping[0][1] :
                self.wheel_data[mapping[1][0]] |= mapping[1][1]
        
        #Override Brake and Accelrate with L2/R2
        if self.gamepad_data[cmb.GAMEPAD_L2[0]] &  cmb.GAMEPAD_L2[1]:
            self.wheel_data[cmb.WHEEL_BRAKEBYTE] = self.gamepad_data[cmb.GAMEPAD_LTRIGGER]

        
        if self.gamepad_data[cmb.GAMEPAD_R2[0]] &  cmb.GAMEPAD_R2[1]:
            print("Trigger accellerator")
            self.wheel_data[cmb.WHEEL_ACCELERATEBYTE] = self.gamepad_data[cmb.GAMEPAD_RTRIGGER]
        

        #Pass steering if not centred

        left_joy_x = self.gamepad_data[cmb.GAMEPAD_LJOY_X]
        if left_joy_x != 0x80:            
            self._map_steering(left_joy_x)

    # 0 to 255
    def _map_steering(self,input):  
        wheel_value = int(input * ( cmb.STEER_MAX / 256))
        self.wheel_data[cmb.WHEEL_WHEEL_HIGHBYTE] = int(wheel_value / 256)
        self.wheel_data[cmb.WHEEL_WHEEL_LOWBYTE] = wheel_value % 256
    
    def _apply_brake(self):
        if self.braking:
            self.wheel_data[cmb.WHEEL_BRAKEBYTE] = 0xFF
            self.wheel_data[cmb.WHEEL_ACCELERATEBYTE] = 0x00
        else:            
            self.wheel_data[cmb.WHEEL_BRAKEBYTE] = 0x00
        self.braking=False


    def start_controller(self):
        start_time = time.time()
        loops = 0
        loopssinceclick=0

        shared_speed_mean = multiprocessing.Value('f')
        shared_steering_angle = multiprocessing.Value('f')

        self.listener = multiprocessing.Process(target=self.sensor_loop,args=(shared_speed_mean,shared_steering_angle))
        self.listener.daemon=True
        self.listener.start()

        self.ui = multiprocessing.Process(target=webui.start_ui,args=(shared_speed_mean,shared_steering_angle,self.speed_offset,self.speed_calibration,self))
        self.ui.daemon = True
        self.ui.start()

        while True:
            time.sleep(0.02)
            self.read_crew_telemetry()
            self.wheel_data = bytearray(cmb.WHEEL_NEUTRAL)

            loops += 1
            loopssinceclick += 1
            now_time = time.time()
            hz = loops / (now_time-start_time)
            latest_gamepad_data = bytearray(self.gamepad.read(GAMEPAD_DATA_LEN))
            clicker_data = bytearray(self.clicker.read(64))

            if len(latest_gamepad_data) == GAMEPAD_DATA_LEN:
                self.gamepad_data = latest_gamepad_data


                
                #Joystick overrides Bike for steering so use if it's neutral
                if self.gamepad_data[cmb.GAMEPAD_LJOY_X] > 0x78 and self.gamepad_data[cmb.GAMEPAD_LJOY_X] < 0x88  :
                    self._set_steering(shared_steering_angle.value)

                self._apply_acceleration(loops,int(shared_speed_mean.value))            
                self._apply_brake()
                self._map_pad_to_wheel() #Gamepad has priority
                self._parse_clicker_data(clicker_data)
                self._send_data()
            else:
                logging.info("No Data from device")


