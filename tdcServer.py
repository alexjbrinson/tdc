#################################################################
#
#
#################################################################
import time
import numpy as np
import pickle
from pcaspy import Driver, SimpleServer
import threading
import sys
import os
from epics import PV

class Counter(Driver):
  def __init__(self, counterBins=1000, liveToFsFile="liveToFs_latest_File.pkl"):
      #EPICS_CA_AUTO_ADDR_LIST="NO"
      os.environ["EPICS_CA_ADDR_LIST"] = "192.168.1.1"
      print("EPICS_CA_ADDR_LIST:", os.environ["EPICS_CA_ADDR_LIST"])
      self.server = SimpleServer()
      self.liveToFsFile=liveToFsFile
      self.prefix = "Beamline:"
      self.counterBins=counterBins
      self.pvdb={}
      self.pvdb["TDC2"] = {"prec" : 0, "units":"none", 'count':counterBins}
      self.pvdb["TDC3"] = {"prec" : 0, "units":"none", 'count':counterBins}
      self.pvdb["TDC4"] = {"prec" : 0, "units":"none", 'count':counterBins}
      self.pvdb["TriggerGroups"] = {"value": 0, "prec" : 0, "units":"none"}
      self.pvdb["LastUpdate"] = {"prec" : 0, "units":"none", 'count':1}
      #for key in self.pvdb.keys(): self.server.createPV(self.prefix, self.pvdb[key])
      self.server.createPV(self.prefix, self.pvdb)
      #os.startfile("C:\\Users\\EMALAB\\AppData\\Roaming\\Python\\Python311\\site-packages\\epics\\clibs\\win64\\caRepeater.exe")
      
      super(Counter, self).__init__()
      self.varNames={"TDC2":"channel 2",
                     "TDC3":"channel 3",
                     "TDC4":"channel 4",
                     "TriggerGroups":"triggerGroups",
                     "LastUpdate":"timeStamp"}
      
      self.tStreamDataDic={"channel 2":counterBins*[0], "channel 3":counterBins*[0], "channel 4":counterBins*[0], 'triggerGroups':-1, 'timeStamp':-1}
      
  def start(self):
    self.updatingStatus = True
    self.updatingThread = threading.Thread(target = self.update, daemon = True)
    self.updatingThread.start()
    self.processing=True
    self.processsingThread = threading.Thread(target = self.processingFunction)
    self.processsingThread.start()

  def stop(self):
    self.updatingStatus = False
    self.processing=False
    self.updatingThread.join()
    self.processsingThread.join()

  def update(self, updateTime=0.2):
    i=0
    while self.updatingStatus:
      try:
        with open(self.liveToFsFile, 'rb') as file:
          self.tStreamDataDic=pickle.load(file); file.close()
      except EOFError: print('oops! file collision, will try again')
      except pickle.UnpicklingError: print('Oh No! My pickles are corrupt!');
      except FileNotFoundError:  pass;#print("no file found. Probably bc you haven't acquired any data yet. Broke ass")
      except Exception as e: print('wahhh!',e); raise(e)
      i+=1
      #if i%10==0: raise(FileNotFoundError)
      #print(self.tStreamDataDic['triggerGroups'])
      #print(self.tStreamDataDic['timeStamp'])
      for key in self.pvdb.keys():
        #print(self.prefix+self.varNames[key])
        #caput(self.prefix+self.varNames[key], self.tStreamDataDic[key])
        self.setParam(key, self.tStreamDataDic[self.varNames[key]])
      self.updatePVs()
      updatePV=PV(self.prefix+"LastUpdate")
      #print("pCASpy test: ",self.read("LastUpdate"))
      #print("epics  test: ", updatePV.get()); updatePV.disconnect()
      #caput("Beamline:TDC3", self.tStreamDataDic['channel 3'])
      #caput("Beamline:LastUpdate", self.tStreamDataDic['timeStamp'])
      #print('this works', i)
      time.sleep(updateTime)

  def processingFunction(self, ptime=0.1):
    while self.processing: self.server.process(ptime)

def main():
  driver = Counter()
  driver.start()
  #time.sleep(5)
  #driver.stop()
  #print('success!')

if __name__== '__main__':
  main()
    