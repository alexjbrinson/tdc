#################################################################
#
#
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

class Counter(Driver):
  def __init__(self, counterBins=1000, liveToFsFile="liveToFs_latest_File.pkl"):
      self.liveToFsFile=liveToFsFile
      self.prefix = "Beamline:"
      pvdbDic={}
      pvdbDic["channel 2"] = {"TDC2":{"prec" : 0, "units":"none", 'count':counterBins}}
      pvdbDic["channel 3"] = {"TDC3":{"prec" : 0, "units":"none", 'count':counterBins}}
      pvdbDic["channel 4"] = {"TDC4":{"prec" : 0, "units":"none", 'count':counterBins}}
      pvdbDic["trigger groups"] = {"trigger groups":{"prec" : 0, "units":"none", 'count':1}}
      pvdbDic["timeStamp"] = {"TDC5":{"prec" : 0, "units":"none", 'count':1}}
      self.server = SimpleServer()
      for key in pvdbDic.keys(): self.server.createPV(self.prefix, pvdbDic[key])
      #self.server.createPV(self.prefix, pvdbDic)
      os.startfile("C:\\Users\\EMALAB\\AppData\\Roaming\\Python\\Python311\\site-packages\\epics\\clibs\\win64\\caRepeater.exe")
      EPICS_CA_AUTO_ADDR_LIST="NO"
      os.environ["EPICS_CA_ADDR_LIST"] = "192.168.1.118"
      print("EPICS_CA_ADDR_LIST:", os.environ["EPICS_CA_ADDR_LIST"])
      super(Counter, self).__init__()
      self.tStreamDataDic={"channel 2":counterBins*[0], "channel 3":counterBins*[0], "channel 4":counterBins*[0], 'triggerGroups':-1, 'timeStamp':time.time()}
      
  def start(self):
    self.run = True
    self.updatingThread = threading.Thread(target = self.update, daemon = True)
    self.updatingThread.start()
    self.processing=True
    self.processsingThread = threading.Thread(target = self.processingFunction)
    self.processsingThread.start()

  def stop(self):
    self.run = False
    self.processing=False
    self.updatingThread.join()
    self.processsingThread.join()

  def update(self, updateTime=0.2):
    i=0
    while self.run:
      try:
        with open(self.liveToFsFile, 'rb') as file:
          self.tStreamDataDic=pickle.load(file); file.close()
      except EOFError: print('oops! file collision, will try again')
      i+=1
      print(self.tStreamDataDic['triggerGroups'])
      print(self.tStreamDataDic['timeStamp'])
      caput("Beamline:TDC2", self.tStreamDataDic['channel 2'])
      caput("Beamline:TDC3", self.tStreamDataDic['channel 3'])
      caput("Beamline:TDC5", -1)#self.tStreamDataDic['timeStamp'])
      print('this works', i)
      time.sleep(updateTime)

  def processingFunction(self, ptime=0.1):
    while self.processing: self.server.process(ptime)



if __name__== '__main__':

    driver = Counter()
    driver.start()
    #time.sleep(5)
    #driver.stop()
    #print('success!')
    
    #driver.processingFunction(ptime=0.1)
    #while True: driver.server.process(0.1)
