# This Python file uses the following encoding: utf-8
#
# Library for Grove - PM2.5 PM10 detect sensor (HM3301)
#
## License
#
# The MIT License (MIT)
#
# Copyright (C) 2018  Seeed Technology Co.,Ltd.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys
import struct
import re
import os.path
import argparse
import requests
from time import time, sleep, localtime, strftime
from configparser import ConfigParser
from smbus2 import SMBus, i2c_msg

HM3301_DEFAULT_I2C_ADDR = 0x40
HM3301_USE_I2C = 0x88
HM3301_DATA_FRAME_SIZE = 29

class HM3301:
    class Error(Exception):
        pass

    def __init__(self, bus=1):
        self.sensor_number = 0

        # Standard particulate matter concentrations in µg/m³
        self.PM_1_0_standard_particulate = 0
        self.PM_2_5_standard_particulate = 0
        self.PM_10_standard_particulate  = 0

        # Atmospheric environment concentration in µg/m³
        self.PM_1_0_atmospheric_environment = 0
        self.PM_2_5_atmospheric_environment = 0
        self.PM_10_atmospheric_environment  = 0

        # Number of particles in 1 liter of air with diameter in µm above
        # I think these are returned on HM-3X02
        self.particles_0_3 = 0
        self.particles_0_5 = 0
        self.particles_1_0 = 0
        self.particles_2_5 = 0
        self.particles_5_0 = 0
        self.particles_10  = 0

        self.bus = SMBus(bus)
        use_i2c = i2c_msg.write(HM3301_DEFAULT_I2C_ADDR, [HM3301_USE_I2C])
        self.bus.i2c_rdwr(use_i2c)

    def read_data(self):
        msg = i2c_msg.read(HM3301_DEFAULT_I2C_ADDR, HM3301_DATA_FRAME_SIZE)

        self.bus.i2c_rdwr(msg)

        data = list(msg)

        if not hm3301.check_crc(data):
            return False

        self.sensor_number = data[2] << 8 | data[3]

        self.PM_1_0_standard_particulate = data[4] << 8 | data[5]
        self.PM_2_5_standard_particulate = data[6] << 8 | data[7]
        self.PM_10_standard_particulate  = data[8] << 8 | data[9]

        self.PM_1_0_atmospheric_environment = data[10] << 8 | data[11]
        self.PM_2_5_atmospheric_environment = data[12] << 8 | data[13]
        self.PM_10_atmospheric_environment  = data[14] << 8 | data[15]

        self.particles_0_3 = data[16] << 8 | data[17]
        self.particles_0_5 = data[18] << 8 | data[19]
        self.particles_1_0 = data[20] << 8 | data[21]
        self.particles_2_5 = data[22] << 8 | data[23]
        self.particles_5_0 = data[24] << 8 | data[25]
        self.particles_10 =  data[26] << 8 | data[27]
        return True

    def check_crc(self,data):
        sum = 0

        for i in range(HM3301_DATA_FRAME_SIZE-1):
            sum += data[i]

        sum = sum & 0xff

        return sum == data[28]

sys.path[0]
config = ConfigParser(delimiters=('=', ), inline_comment_prefixes=('#'))
config.optionxform = str
config.read(os.path.join(sys.path[0], 'config.ini'))

# app settings
makerAPIHostname = config['Hubitat'].get('hostname')
makerAPIToken = config['Hubitat'].get('APIToken')
makerAPIAppID = config['Hubitat'].get('appID')

# device settings
makerAPIDeviceID = config['Hubitat'].get('deviceID')

sleep_period = float(config['General'].get('i2cPeriod', 120))

#---- Initialize ----#
while True:
    hm3301 = HM3301()

    sleep(.1)

    if hm3301.read_data():
        try:
            requests.get("{}/apps/api/{}/devices/{}/setValuePM2_5/{}?access_token={}".format(makerAPIHostname, makerAPIAppID, makerAPIDeviceID, hm3301.PM_2_5_standard_particulate, makerAPIToken))
        except:
            try:
                requests.get("{}/apps/api/{}/devices/{}/errorNotFound/?access_token={}".format(makerAPIHostname, makerAPIAppID, makerAPIDeviceID, makerAPIToken))
            except:
                pass
        finally:
            pass
    else:
            try:
                requests.get("{}/apps/api/{}/devices/{}/errorNotFound/?access_token={}".format(makerAPIHostname, makerAPIAppID, makerAPIDeviceID, makerAPIToken))
            except:
                pass
    sleep(sleep_period)
