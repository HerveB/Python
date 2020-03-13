#!/usr/bin/env python2

#Started with Airthings samples code available at - https://github.com/Airthings/wave-reader

#This is meant to be run as a background daemon on a RPi (I'm using a ZeroW for this project).  It feeds a MakerAPI defined in the Hubitat webapp.
#That then updates the selected device with the current data.  The class I chose to create has a field for PM2.5 but the WavePlus doesn't support that.
#2 of us have asthma issues so it's important to us I've got a sensor to connect to the Pi and when it is done I will likely just add it to the script too.
import sys
import struct
import re
import os.path
import argparse
import requests
from time import time, sleep, localtime, strftime
from configparser import ConfigParser
from bluepy.btle import UUID, Peripheral, Scanner, DefaultDelegate

# ====================================
# Utility functions for WavePlus class
# ====================================

def parseSerialNumber(ManuDataHexStr):
    if (ManuDataHexStr == "None"):
        SN = "Unknown"
    else:
        ManuData = bytearray.fromhex(ManuDataHexStr)

        if (((ManuData[1] << 8) | ManuData[0]) == 0x0334):
            SN  =  ManuData[2]
            SN |= (ManuData[3] << 8)
            SN |= (ManuData[4] << 16)
            SN |= (ManuData[5] << 24)
        else:
            SN = "Unknown"
    return SN

# ===============================
# Class WavePlus
# ===============================

class WavePlus():
    def __init__(self, serialNumber):
        self.periph        = None
        self.curr_val_char = None
        self.SN = serialNumber
        self.MacAddr       = None
        self.uuid          = UUID("b42e2a68-ade7-11e4-89d3-123b93f75cba")

    def connect(self):
        # Auto-discover device on first connection
        if (self.MacAddr is None):
            scanner     = Scanner().withDelegate(DefaultDelegate())
            searchCount = 0
            #I have my wave plus and the pi zero W this runs on mounted directly across from each other in a standard hallway
            #It still fails at 0.1 and 50 more than once a day.
            while self.MacAddr is None and searchCount < 100:
                devices      = scanner.scan(0.2) # 0.1 seconds scan period
                searchCount += 1
                for dev in devices:
                    ManuData = dev.getValueText(255)
                    SN = parseSerialNumber(ManuData)
                    if (str(SN) == str(self.SN)):
                        self.MacAddr = dev.addr # exits the while loop on next conditional check
                        break # exit for loop
            
            if (self.MacAddr is None):
                print("ERROR - Could not find wave plus")
                sys.exit(1)
        
        # Connect to device
        if (self.periph is None):
            self.periph = Peripheral(self.MacAddr)
        if (self.curr_val_char is None):
            self.curr_val_char = self.periph.getCharacteristics(uuid=self.uuid)[0]
        
    def read(self):
        if (self.curr_val_char is None):
            print("ERROR - Device not connected")
            sys.exit(1)            
        rawdata = self.curr_val_char.read()
        rawdata = struct.unpack('BBBBHHHHHHHH', rawdata)
        sensors = Sensors()
        sensors.set(rawdata)
        return sensors
    
    def disconnect(self):
        if self.periph is not None:
            self.periph.disconnect()
            self.periph = None
            self.curr_val_char = None

# ===================================
# Class Sensor and sensor definitions
# ===================================

NUMBER_OF_SENSORS               = 7
SENSOR_IDX_HUMIDITY             = 0
SENSOR_IDX_RADON_SHORT_TERM_AVG = 1
SENSOR_IDX_RADON_LONG_TERM_AVG  = 2
SENSOR_IDX_TEMPERATURE          = 3
SENSOR_IDX_REL_ATM_PRESSURE     = 4
SENSOR_IDX_CO2_LVL              = 5
SENSOR_IDX_VOC_LVL              = 6

class Sensors():
    def __init__(self):
        self.sensor_version = None
        self.sensor_data    = [None]*NUMBER_OF_SENSORS
    
    def set(self, rawData):
        self.sensor_version = rawData[0]
        if (self.sensor_version == 1):
            self.sensor_data[SENSOR_IDX_HUMIDITY]             = rawData[1]/2
            self.sensor_data[SENSOR_IDX_RADON_SHORT_TERM_AVG] = self.conv2radon(rawData[4])
            self.sensor_data[SENSOR_IDX_RADON_LONG_TERM_AVG]  = self.conv2radon(rawData[5])
            self.sensor_data[SENSOR_IDX_TEMPERATURE]          = rawData[6]/100
            self.sensor_data[SENSOR_IDX_REL_ATM_PRESSURE]     = rawData[7]/50.0
            self.sensor_data[SENSOR_IDX_CO2_LVL]              = rawData[8]*1.0
            self.sensor_data[SENSOR_IDX_VOC_LVL]              = rawData[9]*1.0
        else:
            print("ERROR: Unknown sensor version.\n")
            sys.exit(1)
   
    def conv2radon(self, radon_raw):
        radon = "N/A" # Either invalid measurement, or not available
        if 0 <= radon_raw <= 16383:
            radon  = radon_raw * 0.027027027027
        return radon

    def getValue(self, sensor_index):
        return self.sensor_data[sensor_index]

sys.path[0]
config = ConfigParser(delimiters=('=', ), inline_comment_prefixes=('#'))
config.optionxform = str
config.read(os.path.join(sys.path[0], 'config.ini'))

used_adapter = config['General'].get('adapter', 'hci0')

# app settings
makerAPIHostname = config['Hubitat'].get('hostname')
makerAPIToken = config['Hubitat'].get('APIToken')
makerAPIAppID = config['Hubitat'].get('appID')

# device settings
makerAPIDeviceID = config['Hubitat'].get('deviceID')

serialNumber = config['General'].get('SerialNumber')

sleep_period = float(config['General'].get('period', 300))

#---- Initialize ----#
waveplus = WavePlus(serialNumber)

while True:
    try:
        waveplus.connect()
        sensors = waveplus.read()
        print('Read')
    except:
        try:
            requests.get("{}/apps/api/{}/devices/{}/errorNotFound/?access_token={}".format(makerAPIHostname, makerAPIAppID, makerAPIDeviceID, makerAPIToken))
        except:
            pass
    else:
        sensorData = "{},{},{},{},{},{},{}".format( 
            sensors.getValue(SENSOR_IDX_TEMPERATURE), 
            sensors.getValue(SENSOR_IDX_HUMIDITY), 
            sensors.getValue(SENSOR_IDX_REL_ATM_PRESSURE), 
            sensors.getValue(SENSOR_IDX_CO2_LVL), 
            sensors.getValue(SENSOR_IDX_VOC_LVL), 
            sensors.getValue(SENSOR_IDX_RADON_SHORT_TERM_AVG), 
            sensors.getValue(SENSOR_IDX_RADON_LONG_TERM_AVG))
        try:
            requests.get("{}/apps/api/{}/devices/{}/setValuesNoPM2_5/{}?access_token={}".format(makerAPIHostname, makerAPIAppID, makerAPIDeviceID, sensorData, makerAPIToken))
        except:
            pass
    finally:
        waveplus.disconnect()

    sleep(sleep_period)
