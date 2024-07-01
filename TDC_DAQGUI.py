import sqlite3 as sl
from tdcClass import TimeStampTDC1
import TDCutilities as tdcu
import tdcServer as tdcServer
from tdcSettings import SettingsWindow
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
class TDC_GUI(QtWidgets.QMainWindow, Ui_MainWindow):
  def __init__(self, settingsDic={}):
    QtWidgets.QMainWindow.__init__(self); Ui_MainWindow.__init__(self)
    # self.setWindowModality(QtCore.Qt.ApplicationModal)
    self.setupUi(self)
    self.setWindowTitle('TDC GUI') ;#self.setWindowIcon(QIcon('TDC_Icon.png'))
    if settingsDic=={}:
      settingsDic={'int_time':100,
                   'mode':'TTL',
                   'threshold':2.0,
                   'path':'../data/DummyData'}

    self.settingsDic=settingsDic
    self.settingsButton.clicked.connect(self.openSettingsWindow)
    
    self.comPort='COM3' #TODO: Automate this
    self.realData=False; self.hasOldData=False
    try:
      self.device = TimeStampTDC1(self.comPort)
      self.deviceCommunication=True
    except: self.deviceCommunication=False
    print("communicating with device?", self.deviceCommunication)
    self.setSettings()
    
    self.scanToggled=False
    self.getScanNum()
    self.scanToggler.setText('start run '+str(self.scanNum))
    self.scanToggler.clicked.connect(self.beginScan)

    self.oldRuns=[]
    self.oldData=pd.DataFrame({'tStamp':[]})
    self.currentData_totals=pd.DataFrame({'tStamp':[]})
    self.currentData_latest=pd.DataFrame({'tStamp':[]})


    self.tMinValue=int(3E3); self.tMaxValue=int(7E3); self.tBinsValue=int(100) #some values to initialize, and then will update based on the value in self.binsLineEdit
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
    self.usingEpics=False #this is false unless the try below works
    try: self.epicsDriver=tdcServer.Counter(); self.usingEpics=True
    except Exception as e: print('wahhh!',e) ; self.usingEpics=False
    print('initialization end')

  def openSettingsWindow(self):
    self.settingsWindow=SettingsWindow(settingDic=self.settingsDic)
    #self.settingsWindow.aboutToQuit.connect(self.settingsWindow.safeExit)
    self.settingsWindow.submitClicked.connect(self.on_sub_window_confirm)
    # self.settingsWindow.isModal=True
    self.settingsWindow.show()

  def on_sub_window_confirm(self, settingsDic):
    self.settingsDic=settingsDic #update dictionary of settings
    self.setSettings()  #update actual hardware (and some pure software) settings based on updated dictionary
    print('test:',settingsDic)

  def setSettings(self):
    self.int_time=self.settingsDic['int_time'] ; self.mode = self.settingsDic['mode']
    self.threshold=self.settingsDic['threshold']; self.scanDirectory=self.settingsDic['path']
    self.getScanNum(); self.scanToggler.setText('start run '+str(self.scanNum))
    self.settingsLabel.setText('mode = %s ; threshold = %.2f ; integration time =%d ; scanDirectory=%s'%(self.mode,self.threshold,self.int_time,self.scanDirectory))
    if self.deviceCommunication:
      try:
        self.device.level=self.device.TTL_LEVELS if self.mode=='TTL' else self.device.NIM_LEVELS
        self.device.clock='2'#force internal clock
        self.device.threshold=self.threshold
        #self.device.int_time=self.int_time
        print('threshold = ',self.device.threshold)
        print('time?',self.device.int_time)
        print('level?',self.device.level)
      except: print('this failed somehow pls investigate'); quit()

  def getScanNum(self):
    self.previousScans=[]
    if not os.path.exists(self.scanDirectory):self.scanNum=1
    else:
      dirList=os.listdir(self.scanDirectory)
      for item in dirList:
        if 'scan' in item:
          try: self.previousScans+=[int(item.lstrip('scan'))]
          except: pass
  
      try: self.scanNum=1+np.max(self.previousScans)
      except:self.scanNum=1
      print('did it work?', self.scanNum)

  def instantiateDataFiles(self):
    self.getScanNum()
    self.scanDirectoryPrefix=str(self.scanDirectory)+'/scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_'
    os.makedirs(str(self.scanDirectory)+'/scan'+str(self.scanNum)+'/')
    
    #Creating data files for live readout and logging
    self.dbName=self.scanDirectoryPrefix+'allData.db' #TODO: change this
    self.connection = sl.connect(self.dbName)
    self.rawDataFile=self.scanDirectoryPrefix+'currentData.raw'
    self.liveToFs_totals_File=self.scanDirectoryPrefix+"liveToFs_totals_File.pkl"
    self.liveToFs_latest_File=self.scanDirectoryPrefix+"liveToFs_latest_File.pkl"
    self.timeStreamFile=self.scanDirectoryPrefix+'timeStreamLiveData.pkl'

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
        try:
          oldDataPrefix=str(self.scanDirectory)+'/scan'+str(run)+'/scan'+str(run)+'_'
          old_dbName=oldDataPrefix+'allData.db'
          print('test: old_dbName=',old_dbName)
          oldDataConnection = sl.connect(old_dbName)
          print('works up to here?')
          tempFrame=pd.read_sql_query("SELECT * from TDC", oldDataConnection); print(tempFrame)
          self.oldData=pd.concat([self.oldData,pd.read_sql_query("SELECT * from TDC WHERE run="+str(run), oldDataConnection)])
          oldDataConnection.close()
        except: print('failed to load run %d. Does it really even exist?'%run)
      print('test oldData:\n', self.oldData)
      self.hasOldData = True
      self.updatePlotTof_old()

  def endScan(self):
    if self.usingEpics: self.epicsDriver.stop()
    if self.deviceCommunication:
      self.device.stop_continuous_stream_timestamps_to_file()
    self.timer.stop()
    self.scanToggler.clicked.disconnect(self.endScan)
    self.scanToggled=False
    try: self.currentData_totals = pd.read_sql_query("SELECT * from TDC WHERE run="+str(self.scanNum), self.connection) #between scans, I would like "current data" to be re-binnable
    except:pass
    self.scanNum+=1 #increment run number in preparation for next run
    self.scanToggler.clicked.connect(self.beginScan)
    self.scanToggler.setText('start run '+str(self.scanNum))
    self.settingsButton.setEnabled(True)
    self.tMinLineEdit.setEnabled(True)
    self.tMaxLineEdit.setEnabled(True)
    self.tBinsLineEdit.setEnabled(True)


  def beginScan(self):
    self.settingsButton.setEnabled(False)
    self.tMinLineEdit.setEnabled(False)
    self.tMaxLineEdit.setEnabled(False)
    self.tBinsLineEdit.setEnabled(False)
    self.instantiateDataFiles(); print('test: self.scanNum=',self.scanNum)
    self.scanToggler.clicked.disconnect(self.beginScan)
    self.scanToggled=True
    self.scanToggler.clicked.connect(self.endScan)
    self.scanToggler.setText('stop run '+str(self.scanNum))
 
    if self.deviceCommunication:
      self.device.start_continuous_stream_timestamps_to_file(self.rawDataFile, self.dbName, self.scanNum, binRay=[self.tMinValue,self.tMaxValue,self.tBinsValue], int_time=self.int_time,
                                                                    totalToFs_targetFile=self.liveToFs_totals_File, latestToFs_targetFile=self.liveToFs_latest_File,timeStreamFile=self.timeStreamFile)
    if self.usingEpics:
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
    #if self.scanToggled: self.endScan()
    print("Live plotter closed")

def getSettings(d):
  global settingsDic
  settingsDic=d
  print('test:',settingsDic)

if __name__ == "__main__":
  #global settingsDic, app0, app1
  settingsDic={'int_time':500,
               'mode':'NIM',
               'threshold':-1.8,
               'path':'../data/RFQ Tests'}
  #TODO: make this initial setting window work without causing wack ass errors on main window closure.
  # app0 = QtWidgets.QApplication(sys.argv)
  # settingsWindow=SettingsWindow(settingDic=settingsDic);#app0.aboutToQuit.connect(settingsWindow.cancel)#placeholder for setting window
  # settingsWindow.submitClicked.connect(getSettings)
  # settingsWindow.show()
  # app0.exec_()

  app1 = QtWidgets.QApplication(sys.argv)
  window = TDC_GUI(settingsDic=settingsDic)
  app1.aboutToQuit.connect(window.safeExit) #TODO: write safeExit function
  window.show()
  sys.exit(app1.exec_())