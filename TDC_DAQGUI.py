import sqlite3 as sl
from tdcClass import TimeStampTDC1
import TDCutilities as tdcu
import sys
import os
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
# TODO: allow for loading of old datasets to overlay on histogram

qtCreatorFile = "TDCGUI.ui" # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
  def __init__(self):
    #super(MyApp, self).__init__()
    QtWidgets.QMainWindow.__init__(self)
    Ui_MainWindow.__init__(self)
    self.setupUi(self)
    self.dbName='allData.db' #TODO: change this
    self.rawDataFile='currentData.raw'
    self.liveDataFile="iTurnedMyselfIntoAPickle.pkl"
    self.scanCountingFile = 'scanTracker.txt'
    self.comPort='COM3' #TODO: Automate this
    self.connection = sl.connect(self.dbName)
    self.realData=False; self.hasOldData=False

    try:
      self.device = TimeStampTDC1(self.comPort)
      self.deviceCommunication=True
      self.device.level = self.device.TTL_LEVELS
    except: self.deviceCommunication=False

    print("communicating with device?", self.deviceCommunication)
    #self.sleepyTime = 1 #update every 10th of a second
    #self.file=open("dummyData.csv","r")
    #xData = np.linspace(0,10,11); yData = np.random.randn(11)
    self.scanToggled=False
    self.previousScans=[]
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
    self.currentData=pd.DataFrame({'tStamp':[]})
    print('did it work?', self.currentRun)
    #self.scanNum=0+1 #TODO: Find max scan number in directory, and then set this to that + 1
    self.scanToggler.setText('start run '+str(self.currentRun))
    self.scanToggler.clicked.connect(self.beginScan)

    self.tMinValue=0; self.tMaxValue=3E6; self.tBinsValue=1000 #some values to initialize, and then will update based on the value in self.binsLineEdit
    self.tMinLineEdit.setText(str(self.tMinValue)); self.tMaxLineEdit.setText(str(self.tMaxValue)); self.tBinsLineEdit.setText(str(self.tBinsValue))
    self.tMinLineEdit.returnPressed.connect(self.confirmMinTimeBin); self.tMaxLineEdit.returnPressed.connect(self.confirmMaxTimeBin); self.tBinsLineEdit.returnPressed.connect(self.confirmTimeBins)
    self.tMinLabel.setText('Min Time: '+str(self.tMinValue)+str('s'));self.tMaxLabel.setText('Max Time: '+str(self.tMaxValue)+str('s')); self.tBinsLabel.setText('bin count: '+str(self.tBinsValue))    

    self.loadOldRunsLineEdit.returnPressed.connect(self.loadOldRuns);

    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue)#list(range(self.tBinsValue))  # ToF x-axis
    print(len(self.xToF))
    self.yToF = [-1 for _ in range(self.tBinsValue)]
    self.tofPlotWidget.setBackground('#f0f0f0')#('lightGray')
    self.pen1=pg.mkPen(color=(0,0,0), width=2)
    self.pen2=pg.mkPen(color=(255,0,0), width=2)
    self.data_lineToF =  self.tofPlotWidget.plot(self.xToF, self.yToF, pen=self.pen1)
    self.data_lineToF2 =  self.tofPlotWidget.plot(self.xToF, self.yToF, pen=self.pen2)

    # The plotting
    colors = [(0, 0, 0), (45, 5, 61), (84, 42, 55), (150, 87, 60), (208, 171, 141), (255, 255, 255)]; self.cm = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)# color map

    #self.graphWidget.plot(xData,yData,pen=pen)
    #self.tofPlotWidget.setTitle("ToF Spectrum", color="k", size="20pt");
    self.tofPlotWidget.setLabel('left', "<span style=\"color:black;font-size:20px\">counts</span>"); self.tofPlotWidget.setLabel('bottom', "<span style=\"color:black;font-size:20px\">ToF(bin)</span>")
    


    self.timer = QtCore.QTimer()
    self.timer.setInterval(100) #updates every 50 ms
    '''self.timer.timeout.connect(self.update_plot_data)
    self.timer.start()'''

  def confirmMinTimeBin(self):
    if self.scanToggled: pass
    #updates self.fMinValue, but only if it's reasonable
    try:
      tProposed = int(self.tMinLineEdit.text())
      if tProposed<0 or tProposed>self.tMaxValue:
        print("please enter an integer between 0 and tMax"); tProposed = self.tMinValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter an integer value."); tProposed = self.tMinValue #if line entry is trash, then set proposed freq to old value
    self.tMinValue=tProposed; self.tMinLineEdit.setText(str(self.tMinValue))
    self.tMinLabel.setText('Min Time: '+str(self.tMinValue)+str('units'))
    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue)
    self.yToF = [-1 for _ in range(self.tBinsValue)]
    if self.realData: self.updatePlotTof()
    if self.hasOldData: self.updatePlotTof2()

  def confirmMaxTimeBin(self):
    if self.scanToggled: pass
    #updates self.fMaxValue, but only if it's reasonable
    try:
      tProposed = int(self.tMaxLineEdit.text())
      if tProposed<self.tMinValue or tProposed>20000000:
        print("please enter an integer between tMin and 2000 (units?)"); tProposed = self.tMaxValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter an integer value."); tProposed = self.tMaxValue #if line entry is trash, then set proposed freq to old value
    self.tMaxValue=tProposed; self.tMaxLineEdit.setText(str(self.tMaxValue))
    self.tMaxLabel.setText('Max Time: '+str(self.tMaxValue)+str('units'))
    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue)
    self.yToF = [-1 for _ in range(self.tBinsValue)]
    if self.realData: self.updatePlotTof()
    if self.hasOldData: self.updatePlotTof2()

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
    self.yToF = [-1 for _ in range(self.tBinsValue)]
    if self.realData: self.updatePlotTof()
    if self.hasOldData: self.updatePlotTof2()

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
        self.oldData=self.oldData.append(pd.read_sql_query("SELECT * from TDC WHERE run="+str(run), self.connection))
      print('test oldData:\n', self.oldData)
      self.hasOldData = True
      self.updatePlotTof2()

  def endScan(self):
    if self.deviceCommunication:
      self.device.stop_continuous_stream_timestamps_to_file()
    self.timer.stop()
    self.scanToggler.clicked.disconnect(self.endScan)
    self.scanToggled=False
    self.currentRun+=1
    self.scanToggler.clicked.connect(self.beginScan)
    self.scanToggler.setText('start run '+str(self.currentRun))
    #self.fMinLineEdit.setEnabled(True)
    #self.fMaxLineEdit.setEnabled(True)
    #self.fBinsLineEdit.setEnabled(True)

  def beginScan(self):
    #self.tMinLineEdit.setEnabled(False)
    #self.tMaxLineEdit.setEnabled(False)
    #self.tBinsLineEdit.setEnabled(False)
    with open('scanTracker.txt','w') as f:
        f.write(str(self.currentRun)); f.close()
    self.scanToggler.clicked.disconnect(self.beginScan)
    self.scanToggled=True
    self.scanToggler.clicked.connect(self.endScan)
    self.scanToggler.setText('stop run '+str(self.currentRun))

    if self.deviceCommunication:
      self.device.start_continuous_stream_timestamps_to_file(self.rawDataFile, self.dbName, self.currentRun, binRay=[self.tMinValue,self.tMaxValue,self.tBinsValue], pickleDic=self.liveDataFile)
    self.realData = True
    self.timer.timeout.connect(self.updateEverything)
    self.timer.start()

  def updateEverything(self):
    if not self.scanToggled:
      print('investigate this!'); quit()
    #time.sleep(self.sleepyTime)
    with open(self.liveDataFile, 'rb') as file:
      self.currentData=pickle.load(file)
    self.updatePlotTof()

  def updatePlotTof(self):
    self.yToF = self.currentData["channel 2"] #TODO: Eventually allow to switch channels
    self.data_lineToF.setData(self.xToF, self.yToF, pen=self.pen1)

  def updatePlotTof2(self):
    self.yToF2, bins =np.histogram(np.array(self.oldData.tStamp), bins=self.xToF)
    self.data_lineToF2.setData( (bins[1:]+bins[:-1])/2, self.yToF2, pen=self.pen2)
    #self.data_lineToF.setData(self.xToF, self.yToF, pen=self.pen1)

  def safeExit():
    print("Live plotter closed")

if __name__ == "__main__":
  app = QtWidgets.QApplication(sys.argv)
  app.aboutToQuit.connect(MyApp.safeExit) #TODO: write safeExit function
  window = MyApp()
  window.show()
  sys.exit(app.exec_())

#TODO: understand occasional (and seemingly inconsequential) error on pickle load call: "EOFError: Ran out of input"