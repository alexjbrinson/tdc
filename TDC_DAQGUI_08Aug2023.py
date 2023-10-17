import sqlite3 as sl
from tdcClass import TimeStampTDC1
import TDCutilities as tdcu
import tdcServer as tdcServer
import sys, os
import time
from PyQt5 import QtCore, QtGui, QtWidgets, uic
import numpy as np
from pyqtgraph import PlotWidget
import pyqtgraph as pg
from random import randint
import socket
import pandas as pd
import math
from datetime import datetime
import pickle

#np.set_printoptions(threshold=np.inf)

qtCreatorFile = "TDCGUI_MultiWindow.ui" # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

#TODO: send stop command to TDC before attempting re-connect
class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
  def __init__(self):
    self.int_time=500
    #super(MyApp, self).__init__()
    QtWidgets.QMainWindow.__init__(self)
    Ui_MainWindow.__init__(self)
    self.setupUi(self)
    self.setWindowTitle('TDC GUI')
    #self.setWindowIcon(QIcon('TDC_Icon.png'))
    self.dbName='allData.db' #TODO: change this
    self.rawDataFile='currentData.raw'
    self.liveToFs_totals_File="liveToFs_totals_File.pkl"
    self.liveToFs_latest_File="liveToFs_latest_File.pkl"
    self.timeStreamFile='timeStreamLiveData.pkl'
    self.scanCountingFile = 'scanTracker.txt'
    self.comPort='COM13' #TODO: Automate this
    self.connection = sl.connect(self.dbName)
    self.realData=False; self.hasOldData=False

    try:
      self.device = TimeStampTDC1(self.comPort)
      self.deviceCommunication=True
      self.device.level = self.device.NIM_LEVELS#self.device.TTL_LEVELS#
      self.device.clock='2'#force internal clock
    except: self.deviceCommunication=False
    print("communicating with device?", self.deviceCommunication)
    print('threshold = ',self.device.threshold)
    print('time?',self.device.int_time)
    #self.device.int_time = 0.001
    #print('time?',self.device.int_time)
    self.device.threshold=-.25
    print('threshold = ',self.device.threshold)

    self.scanToggled=False
    try: 
      with open(self.scanCountingFile,'r') as f:
        self.currentRun=int(f.readline())+1
        f.close()
        print("successfully read run number")
    except:
      self.currentRun=0
      with open(self.scanCountingFile,'w') as f:
        f.write(str(self.currentRun)); f.close()

    
    self.oldRuns=[]
    self.oldData=pd.DataFrame({'tStamp':[]})
    self.currentData_totals=pd.DataFrame({'tStamp':[]})
    self.currentData_latest=pd.DataFrame({'tStamp':[]})
    print('did it work?', self.currentRun)
    #self.scanNum=0+1 #TODO: Find max scan number in directory, and then set this to that + 1
    self.scanToggler.setText('start run '+str(self.currentRun))
    self.scanToggler.clicked.connect(self.beginScan)

    self.tMinValue=int(4E3); self.tMaxValue=int(7E3); self.tBinsValue=int(100) #some values to initialize, and then will update based on the value in self.binsLineEdit
    self.tMinLineEdit.setText(str(self.tMinValue)); self.tMaxLineEdit.setText(str(self.tMaxValue)); self.tBinsLineEdit.setText(str(self.tBinsValue))
    self.tMinLineEdit.returnPressed.connect(self.confirmMinTimeBin); self.tMaxLineEdit.returnPressed.connect(self.confirmMaxTimeBin); self.tBinsLineEdit.returnPressed.connect(self.confirmTimeBins)
    self.tMinLabel.setText('Min Time: '+str(self.tMinValue)+str('s'));self.tMaxLabel.setText('Max Time: '+str(self.tMaxValue)+str('s')); self.tBinsLabel.setText('bin count: '+str(self.tBinsValue))    

    self.timeStreamLength=100
    self.xTimeStream=np.linspace(0, self.timeStreamLength-1,self.timeStreamLength)
    self.yTimeStream=self.timeStreamLength*[0]

    self.loadOldRunsLineEdit.returnPressed.connect(self.loadOldRuns);

    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue+1)#list(range(self.tBinsValue))  # ToF x-axis
    print(len(self.xToF))
    self.yToF_total = [-1]*(self.tBinsValue+1)
    self.yToF_latest = [0]*(self.tBinsValue+1)
    self.yToF_old = [0]*(self.tBinsValue+1)
    self.tofPlotWidget.setBackground('#f0f0f0')#('lightGray')
    self.pen1=pg.mkPen(color=(0,0,0), width=2)
    self.pen2=pg.mkPen(color=(255,0,0), width=2)
    self.pen3=pg.mkPen(color=(0,0,255), width=2)
    self.data_lineToF =  self.tofPlotWidget.plot(self.xToF, self.yToF_total, pen=self.pen1)
    self.data_lineToF_old =  self.tofPlotWidget.plot(self.xToF, self.yToF_old, pen=self.pen2)
    self.data_lineToF_latest =  self.tofPlotWidget.plot(self.xToF, self.yToF_latest, pen=self.pen3)
    self.data_line_tStream =  self.timeStreamPlotWidget.plot(self.xTimeStream, self.yTimeStream, pen=self.pen1)

    # The plotting
    #self.tofPlotWidget.setTitle("ToF Spectrum", color="k", size="20pt");
    self.tofPlotWidget.setLabel('left', "<span style=\"color:black;font-size:20px\">counts</span>"); self.tofPlotWidget.setLabel('bottom', "<span style=\"color:black;font-size:20px\">ToF(ns)</span>")
    
    self.timer = QtCore.QTimer()
    self.timer.setInterval(100) #update time in ms
    try: self.epicsDriver=tdcServer.Counter()
    except Exception as e: print('wahhh!',e); quit()
    print('initialization end')
    

  def confirmMinTimeBin(self):
    if self.scanToggled: pass
    #updates self.fMinValue, but only if it's reasonable
    try:
      tProposed = int(self.tMinLineEdit.text())
      if tProposed<0 or tProposed>self.tMaxValue:
        print("please enter an integer between 0 and tMax (nanoseconds)."); tProposed = self.tMinValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter an integer value."); tProposed = self.tMinValue #if line entry is trash, then set proposed freq to old value
    self.tMinValue=tProposed; self.tMinLineEdit.setText(str(self.tMinValue))
    self.tMinLabel.setText('Min Time: '+str(self.tMinValue)+str('units'))
    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue+1)
    self.yToF_total = [-1]*(self.tBinsValue+1)
    self.updatePlotTof_total()
    self.updatePlotTof_latest()
    self.updatePlotTof_old()

  def confirmMaxTimeBin(self):
    if self.scanToggled: pass
    #updates self.fMaxValue, but only if it's reasonable
    try:
      tProposed = int(self.tMaxLineEdit.text())
      if tProposed<self.tMinValue or tProposed>2E9:
        print("please enter an integer between tMin and 2*10^9 (nanoseconds)."); tProposed = self.tMaxValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter an integer value."); tProposed = self.tMaxValue #if line entry is trash, then set proposed freq to old value
    self.tMaxValue=tProposed; self.tMaxLineEdit.setText(str(self.tMaxValue))
    self.tMaxLabel.setText('Max Time: '+str(self.tMaxValue)+str('units'))
    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue+1)
    self.yToF_total = [-1]*(self.tBinsValue+1)
    self.updatePlotTof_total()
    self.updatePlotTof_latest()
    self.updatePlotTof_old()

  def confirmTimeBins(self):
    if self.scanToggled: pass
    #updates self.fBinsValue, but only if it's reasonable
    try:
      binsProposed = int(self.tBinsLineEdit.text())
      if binsProposed<2 or binsProposed>100000000:
        print("please enter an integer between 2 and 100000000"); binsProposed = self.tBinsValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter an integer value."); binsProposed = self.tBinsValue #if line entry is trash, then set proposed freq to old value
    self.tBinsValue=binsProposed; self.tBinsLineEdit.setText(str(self.tBinsValue))
    self.tBinsLabel.setText('bin count: '+str(self.tBinsValue))
    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue+1)
    self.yToF_total = [-1]*(self.tBinsValue+1)
    #if self.realData: self.updatePlotTof_total()
    #if self.hasOldData: self.updatePlotTof_old()
    self.updatePlotTof_total()
    self.updatePlotTof_latest()
    self.updatePlotTof_old()

  def loadOldRuns(self):
    oldRunsString=self.loadOldRunsLineEdit.text()
    try:
      oldRunsList=[int(x) for x in oldRunsString.split(',')]; success=True
    except:
      print('Please provide comma-delimited scan numbers, and nothing more')
      oldRunsList=self.oldRuns; success=False
    self.oldRuns=oldRunsList
    self.loadOldRunsLineEdit.setText(str(oldRunsList).strip('[]'))
    if success:
      self.oldData=pd.DataFrame()
      for run in self.oldRuns:
        self.oldData=pd.concat([self.oldData,pd.read_sql_query("SELECT * from TDC WHERE run="+str(run), self.connection)])
      print('test oldData:\n', self.oldData)
      self.hasOldData = True
      self.updatePlotTof_old()

  def endScan(self):
    self.epicsDriver.stop()
    if self.deviceCommunication:
      self.device.stop_continuous_stream_timestamps_to_file()
    self.timer.stop()
    self.scanToggler.clicked.disconnect(self.endScan)
    self.scanToggled=False
    self.currentData_totals = pd.read_sql_query("SELECT * from TDC WHERE run="+str(self.currentRun), self.connection) #between scans, I would like "current data" to be re-binnable
    self.currentRun+=1 #increment run number in preparation for next run
    self.scanToggler.clicked.connect(self.beginScan)
    self.scanToggler.setText('start run '+str(self.currentRun))

  def beginScan(self):
    #self.tMinLineEdit.setEnabled(False)
    #self.tMaxLineEdit.setEnabled(False)
    #self.tBinsLineEdit.setEnabled(False)
    with open(self.scanCountingFile,'w') as f:
        f.write(str(self.currentRun)); f.close()
    self.scanToggler.clicked.disconnect(self.beginScan)
    self.scanToggled=True
    self.scanToggler.clicked.connect(self.endScan)
    self.scanToggler.setText('stop run '+str(self.currentRun))
 
    if self.deviceCommunication:
      self.device.start_continuous_stream_timestamps_to_file(self.rawDataFile, self.dbName, self.currentRun, binRay=[self.tMinValue,self.tMaxValue,self.tBinsValue],
                                                                    totalToFs_targetFile=self.liveToFs_totals_File, latestToFs_targetFile=self.liveToFs_latest_File, int_time=self.int_time)
    try:self.epicsDriver.start()
    except Exception as e: print('wahhh!',e); self.safeExit(); #exit()
    self.realData = True
    self.timer.timeout.connect(self.updateEverything)
    self.timer.start()

  def updateEverything(self):
    if not self.scanToggled:
      print('investigate this!'); quit()
    #time.sleep(self.sleepyTime)
    try:
      with open(self.liveToFs_totals_File, 'rb') as file: self.currentData_totals=pickle.load(file); file.close()
      self.updatePlotTof_total()
    except EOFError: print("oops! file collision on liveToFs_totals_File. But don't worry: this should resolve by next update call")
    except FileNotFoundError: pass;# print("no file found. Probably bc you haven't acquired any data yet. Broke ass")

    try:
      with open(self.liveToFs_latest_File, 'rb') as file: self.currentData_latest=pickle.load(file); file.close()
      self.updatePlotTof_latest()
    except EOFError: print("oops! file collision on liveToFs_latest_File. But don't worry: this should resolve by next update call")
    except FileNotFoundError:  pass;# print("no file found. Probably bc you haven't acquired any data yet. Broke ass")
    
    try:
      with open(self.timeStreamFile, 'rb') as file: self.tStreamDataDic=pickle.load(file); file.close()
      self.tStreamData=self.tStreamDataDic['channel 3']
      #print('mean rate = %.3f +- %.3f'%(np.mean(self.tStreamData), np.std(self.tStreamData)/np.sqrt(len(self.tStreamData))))#reports mean and std error of counts/trigger group
      self.updateTimeStream()
    except EOFError: print("oops! file collision on timeStreamFile. But don't worry: this should resolve by next update call")
    except FileNotFoundError: pass;# print("no file found. Probably bc you haven't acquired any data yet. Broke ass")
    
    
  def updatePlotTof_total(self):
    if self.realData:
      if self.scanToggled: self.yToF_total = self.currentData_totals["channel 3"] #TODO: Eventually allow to switch channels
      else: self.yToF_total, bins =np.histogram(np.array(self.currentData_totals.tStamp), bins=self.xToF)
    else: self.yToF_total = [-1]*(self.tBinsValue)
    self.data_lineToF.setData((self.xToF[1:]+self.xToF[:-1])/2, self.yToF_total, pen=self.pen1)

  def updatePlotTof_latest(self):
    if self.realData and self.scanToggled:
      self.yToF_latest = self.currentData_latest["channel 3"] #TODO: Eventually allow to switch channels
    else: self.yToF_latest = np.zeros(self.tBinsValue)
    self.data_lineToF_latest.setData((self.xToF[1:]+self.xToF[:-1])/2, -self.yToF_latest, pen=self.pen3)

  def updatePlotTof_old(self):
    if self.hasOldData:
      self.yToF_old, bins =np.histogram(np.array(self.oldData.tStamp), bins=self.xToF)
      self.data_lineToF_old.setData( (bins[1:]+bins[:-1])/2, self.yToF_old, pen=self.pen2)
    else: self.yToF_old = [-1]*(self.tBinsValue); bins = self.xToF
    self.data_lineToF_old.setData( (bins[1:]+bins[:-1])/2, self.yToF_old, pen=self.pen2)
    #self.data_lineToF.setData(self.xToF, self.yToF, pen=self.pen1)

  def updateTimeStream(self):
    if len(self.tStreamData)<self.timeStreamLength:
      self.yTimeStream=(self.timeStreamLength-len(self.tStreamData))*[0]+self.tStreamData
    else: self.yTimeStream=self.tStreamData
    self.data_line_tStream.setData(self.xTimeStream, self.yTimeStream, pen=self.pen2)


  def safeExit(self):
    if self.scanToggled: self.endScan()
    print("Live plotter closed")

if __name__ == "__main__":
  app = QtWidgets.QApplication(sys.argv)
  window = MyApp()
  app.aboutToQuit.connect(window.safeExit) #TODO: write safeExit function
  window.show()
  sys.exit(app.exec_())