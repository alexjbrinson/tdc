#################################################################
# This example shows how to read grouped data from the TDC8HP.
# TDC-driver version 3.9.3 must be installed
#################################################################
import time
import ctypes
import numpy as np
import pickle
from pcaspy import Driver, SimpleServer
import threading
import sys
import os
from epics import caget, caput


liveDataFile="liveToFs_latest_File.pkl"

live_readout = True


class Counter(Driver):
    def __init__(self):
        
        pvdb = {"counts":{"prec" : 0, "units":"none", 'count':1000}}
        os.startfile("C:\\Users\\EMALAB\\AppData\\Roaming\\Python\\Python311\\site-packages\\epics\\clibs\\win64\\caRepeater.exe")
        EPICS_CA_AUTO_ADDR_LIST="NO"
        os.environ["EPICS_CA_ADDR_LIST"] = "192.168.1.118"
        print("EPICS_CA_ADDR_LIST:", os.environ["EPICS_CA_ADDR_LIST"])
        
        super(Counter, self).__init__()
        self.run = True
        self.i=0

        

def update():
    i=0
    while True:
        with open(liveDataFile, 'rb') as file:
            tStreamDataDic=pickle.load(file); file.close()
        i+=1
        print(tStreamDataDic)
        caput("Beamline:counts", tStreamDataDic['channel 3'])
        print('this works', i)

        time.sleep(.2)


if __name__== '__main__':
    prefix = "Beamline:"
    server = SimpleServer()
    server.createPV(prefix, pvdb)
    driver = Counter()
    tid = threading.Thread(target = update, daemon = True)
    tid.start()
    

    count = 0

    while True:
        server.process(0.1)
