#written by Alex Brinson (brinson@mit.edu, alexjbrinson@gmail.com) on behalf of EMA Lab
from epics import PV, caget
import sqlite3 as sl
from tdcClass import TimeStampTDC1
import TDCutilities as tdcu
import tdcServer_06Aug2023 as tdcServer
import sys, os, time
from PyQt5 import QtCore, QtGui, QtWidgets, uic
import numpy as np
#from pyqtgraph import PlotWidget
import pyqtgraph as pg
#import socket
import pandas as pd
from datetime import datetime
import pickle

#np.set_printoptions(threshold=np.inf)
# TODO: allow for loading of old datasets to overlay on histogram

qtCreatorFile = "SpectroscopyGUI_NormalAndComplete.ui" # Enter file here.
Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):
  def __init__(self):
    self.int_time=1000 #TODO: add line edit for this
    self.fMinAbsolute=1000
    self.fMaxAbsolute=20000
    #self.lastUpdateTime=caget('Beamline:LastUpdate')
    
    QtWidgets.QMainWindow.__init__(self)
    Ui_MainWindow.__init__(self)
    self.setupUi(self)
    self.setWindowTitle('EMA LAB DAQ')
    #self.setWindowIcon(QIcon('DAQ_Icon.png')) #TODO
        
    self.comPort='COM13' #TODO: Automate this
    self.realData=False; self.hasOldData=False
    try:
      self.device = TimeStampTDC1(self.comPort)
      self.deviceCommunication=True
      self.device.level = self.device.NIM_LEVELS#self.device.TTL_LEVELS#
      self.device.clock='2'#force internal clock
      print('threshold = ',self.device.threshold)
      print('time?',self.device.int_time)
      self.device.threshold=-.25
      print('threshold = ',self.device.threshold)
    except: self.deviceCommunication=False

    print("communicating with device?", self.deviceCommunication)
    
    self.scanToggled=False
    self.previousScans=[]

    dirList=os.listdir()
    for item in dirList:
      if 'scan' in item:
        try: self.previousScans+=[int(item.lstrip('scan'))]
        except: pass

    try: self.scanNum=1+np.max(self.previousScans); print('did it work?', self.scanNum)
    except:self.scanNum=1

    #Creating data files for live readout and logging
    self.dbName='allData.db' #TODO: change this
    self.rawDataFile='currentData.raw'
    self.liveToFs_totals_File="liveToFs_totals_File.pkl"
    self.liveToFs_latest_File="liveToFs_latest_File.pkl"
    self.timeStreamFile='timeStreamLiveData.pkl'
    self.scanCountingFile = 'scanTracker.txt'
    self.connection = sl.connect(self.dbName)

    self.oldRuns=[]
    self.oldData=pd.DataFrame({'tStamp':[]})
    self.currentData_totals=pd.DataFrame({'tStamp':[]})
    self.currentData_latest=pd.DataFrame({'tStamp':[]})
    #self.loadOldRunsLineEdit.returnPressed.connect(self.loadOldRuns); #TODO: Add a qLineEdit for this

    #self.scanNum=0+1 #TODO: Find max scan number in directory, and then set this to that + 1
    self.scanToggler.setText('start scan '+str(self.scanNum))
    self.scanToggler.clicked.connect(self.beginScan)

    #initializing frequency bin settings, connecting update functions to GUI
    self.fMinValue=12545; self.fMaxValue=12549; self.fBinsValue=20 #some values to initialize, and then will update based on the value in self.binsLineEdit
    self.fMinLineEdit.setText(str(self.fMinValue)); self.fMaxLineEdit.setText(str(self.fMaxValue)); self.fBinsLineEdit.setText(str(self.fBinsValue))
    self.fMinLineEdit.returnPressed.connect(self.confirmMinFrequency); self.fMaxLineEdit.returnPressed.connect(self.confirmMaxFrequency); self.fBinsLineEdit.returnPressed.connect(self.confirmFrequencyBins)
    self.fMinLabel.setText('Min Freq: '+str(self.fMinValue)+str('1/cm'));self.fMaxLabel.setText('Max Freq: '+str(self.fMaxValue)+str('1/cm')); self.fBinsLabel.setText('Freq Bins: '+str(self.fBinsValue))    
    
    #initializing ToF bin settings, connecting update functions to GUI
    self.tMinValue=int(4E3); self.tMaxValue=int(7E3); self.tBinsValue=int(100) #some values to initialize, and then will update based on the value in self.binsLineEdit
    self.tMinLineEdit.setText(str(self.tMinValue)); self.tMaxLineEdit.setText(str(self.tMaxValue)); self.tBinsLineEdit.setText(str(self.tBinsValue))
    self.tMinLineEdit.returnPressed.connect(self.confirmMinTimeBin); self.tMaxLineEdit.returnPressed.connect(self.confirmMaxTimeBin); self.tBinsLineEdit.returnPressed.connect(self.confirmTimeBins)
    self.tMinLabel.setText('Min Time: '+str(self.tMinValue)+str('s'));self.tMaxLabel.setText('Max Time: '+str(self.tMaxValue)+str('s')); self.tBinsLabel.setText('bin count: '+str(self.tBinsValue))    

    #The pens I use to draw my plots
    self.pen1=pg.mkPen(color=(0,0,0),  width=2)  #Black
    self.pen2=pg.mkPen(color=(255,0,0), width=1) #Red
    self.pen3=pg.mkPen(color=(0,0,255), width=2) #Blue
    self.pen4=pg.mkPen(color=(0,0,0),  width=1)  #Black
    #Setting some plot backgrounds to light gray to blend in with overall GUI background
    self.tofPlotWidget.setBackground('#f0f0f0'); self.freqPlotWidget.setBackground('#f0f0f0'); self.imagePlotWidget.setBackground('#f0f0f0')

    self.timeStreamLength=100 #TODO: Make this adjustable in GUI?
    self.xTimeStream=np.linspace(0, self.timeStreamLength-1,self.timeStreamLength)
    self.yTimeStream=self.timeStreamLength*[0]

    self.xToF = np.linspace(self.tMinValue, self.tMaxValue, self.tBinsValue+1) # ToF x-axis
    self.yToF_total = [-1]*(self.tBinsValue+1)
    self.yToF_latest = [0]*(self.tBinsValue+1)
    self.yToF_old = [0]*(self.tBinsValue+1)
    self.data_lineToF =  self.tofPlotWidget.plot(self.xToF, self.yToF_total, pen=self.pen1)
    self.data_lineToF_old =  self.tofPlotWidget.plot(self.xToF, self.yToF_old, pen=self.pen2)
    self.data_lineToF_latest =  self.tofPlotWidget.plot(self.xToF, self.yToF_latest, pen=self.pen3)
    self.data_line_tStream =  self.timeStreamPlotWidget.plot(self.xTimeStream, self.yTimeStream, pen=self.pen1)

    self.xFreq = [-1 for _ in range(self.fBinsValue)]  # 2 data points
    self.yFreq = np.linspace(self.fMinValue, self.fMaxValue, self.fBinsValue)  # frequency bins
    self.xIntegTime = [0 for _ in range(self.fBinsValue)]
    
    self.data_lineIntegTime =  self.freqPlotWidget.plot(self.xIntegTime, self.yFreq, pen=self.pen2, symbol='o', symbolPen=pg.mkPen(color=(255, 0, 0), width=5), symbolBrush=pg.mkBrush(0, 0, 255, 255), symbolSize=5)
    self.data_lineFreq =  self.freqPlotWidget.plot(self.xFreq, self.yFreq, pen=None, symbol='o')
    self.data_lineFreqErrors = pg.ErrorBarItem(x=np.array(self.xFreq), y=np.array(self.yFreq), left=np.sqrt(self.yFreq), right=np.sqrt(self.yFreq), pen=self.pen4)
    self.freqPlotWidget.addItem(self.data_lineFreqErrors)
    self.imageData=np.zeros((self.tBinsValue+1, len(self.yFreq)))
    self.currentFreqPoint=self.freqPlotWidget.plot([self.xFreq[0]], [self.yFreq[0]], pen=None, symbol=None, symbolPen=pg.mkPen(color=(0, 255, 0), width=0), symbolBrush=pg.mkBrush(0, 0, 255, 255), symbolSize=5)
    self.currentIntegPoint=self.freqPlotWidget.plot([self.xIntegTime[0]], [self.yFreq[0]], pen=None, symbol=None, symbolPen=pg.mkPen(color=(0, 255, 0), width=5), symbolBrush=pg.mkBrush(0, 0, 255, 255), symbolSize=5)

    # The plotting
    colors = [(0, 0, 0), (45, 5, 61), (84, 42, 55), (150, 87, 60), (208, 171, 141), (255, 255, 255)]; self.cm = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)# color map
    self.img = pg.ImageItem() #creating a pyqtgraph image item object
    self.img.setImage(self.imageData)
    self.img.setColorMap(self.cm)
    self.imagePlotWidget.addItem(self.img)

    #self.tofPlotWidget.setTitle("ToF Spectrum", color="k", size="20pt");
    self.tofPlotWidget.setLabel('left', "<span style=\"color:black;font-size:20px\">counts</span>"); self.tofPlotWidget.setLabel('bottom', "<span style=\"color:black;font-size:20px\">ToF(ns)</span>")
    self.freqPlotWidget.setLabel('left', "<span style=\"color:black;font-size:20px\">freq(1/cm)</span>"); self.freqPlotWidget.setLabel('bottom', "<span style=\"color:black;font-size:20px\">count rate </span>"+"<span style=\"color:red;font-size:20px\"> (integration time)</span>")
    #self.imagePlotWidget.setTitle("Tof-frequency 2D Image", color="k", size="20pt")    

    self.lineEditList=[self.fMinLineEdit,self.fMaxLineEdit,self.fBinsLineEdit]#for windows screensaver shenannigans

    self.timer = QtCore.QTimer()
    self.timer.setInterval(100) #updates every 100 ms

    try: self.epicsDriver=tdcServer.Counter()
    except Exception as e: print('wahhh!',e); quit()
    print('initialization end')

  def confirmMinFrequency(self):
    #updates self.fMinValue, but only if it's reasonable
    try:
      fProposed = float(self.fMinLineEdit.text())
      if fProposed<self.fMinAbsolute or fProposed>self.fMaxAbsolute:
        print("please enter a value between %.5f and %.5f"%(self.fMinAbsolute, self.fMaxAbsolute)); fProposed = self.fMinValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter a valid float value."); fProposed = self.fMinValue #if line entry is trash, then set proposed freq to old value
    self.fMinValue=fProposed; self.fMinLineEdit.setText(str(self.fMinValue))
    self.fMinLabel.setText('Min Freq: '+str(self.fMinValue)+str('THz'))

  def confirmMaxFrequency(self):
    #updates self.fMaxValue, but only if it's reasonable
    try:
      fProposed = float(self.fMaxLineEdit.text())
      if fProposed<self.fMinAbsolute or fProposed>self.fMaxAbsolute:
        print("please enter a value between %.5f and %.5f"%(self.fMinAbsolute, self.fMaxAbsolute)); fProposed = self.fMaxValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter a valid float value."); fProposed = self.fMaxValue #if line entry is trash, then set proposed freq to old value
    self.fMaxValue=fProposed; self.fMaxLineEdit.setText(str(self.fMaxValue))
    self.fMaxLabel.setText('Max Freq: '+str(self.fMaxValue)+str('THz'))

  def confirmFrequencyBins(self):
    #updates self.fBinsValue, but only if it's reasonable
    try:
      binsProposed = int(self.fBinsLineEdit.text())
      if binsProposed<2 or binsProposed>1000:
        print("please enter an integer between 2 and 1000"); binsProposed = self.fBinsValue #if line entry is trash, then set proposed freq to old value
    except: print("please enter an integer value."); binsProposed = self.fBinsValue #if line entry is trash, then set proposed freq to old value
    self.fBinsValue=binsProposed; self.fBinsLineEdit.setText(str(self.fBinsValue))
    self.fBinsLabel.setText('Freq Bins: '+str(self.fBinsValue))

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

  def endScan(self):
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_finalIntegrationTimes.csv', self.integrationTimes)
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_finalImageCounts.csv', self.imageTotals)
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_frequencyBins.csv', self.yFreq)
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_ToFBins.csv', self.xToF)

    #in principle, I should be able to recover below files from image counts and integration totals
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_finalImageSignal.csv', self.imageData)
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_finalSpectrumCounts.csv', self.fCounts)
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_finalSpectrumSignal.csv', self.fSignal)
    np.savetxt('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'_finalTimeOfFlightCounts.csv', self.tofTotals)

    print('integration Times:',self.integrationTimes)
    print('frequency Counts:',self.fCounts)
    print('frequency signal:',self.fSignal)
    self.epicsDriver.stop()
    if self.deviceCommunication:
      self.device.stop_continuous_stream_timestamps_to_file()
    self.timer.timeout.disconnect(self.updateEverything) #It looks like I removed this in TDC_DAQGUI, and it still worked? TODO: figure out what this does
    self.timer.stop()
    self.taggerFile.close()
    self.wmFile.close()
    self.currentData_totals = pd.read_sql_query("SELECT * from TDC WHERE run="+str(self.currentRun), self.connection) #between scans, I would like "current data" to be re-binnable
    self.scanToggler.clicked.disconnect(self.endScan)
    self.scanToggled=False
    self.scanNum+=1
    self.scanToggler.clicked.connect(self.beginScan)
    self.scanToggler.setText('start scan '+str(self.scanNum))
    #bin settings can be adjusted between scans
    self.fMinLineEdit.setEnabled(True); self.fMaxLineEdit.setEnabled(True); self.fBinsLineEdit.setEnabled(True)
    self.tMinLineEdit.setEnabled(True); self.tMaxLineEdit.setEnabled(True); self.tBinsLineEdit.setEnabled(True)

  def beginScan(self):
    #bin settings can't be adjusted during scan. This allows me to generate histograms much more efficiently as datasets grow large.
    self.fMinLineEdit.setEnabled(False); self.fMaxLineEdit.setEnabled(False); self.fBinsLineEdit.setEnabled(False)
    self.tMinLineEdit.setEnabled(False); self.tMaxLineEdit.setEnabled(False); self.tBinsLineEdit.setEnabled(False)
    self.scanToggler.clicked.disconnect(self.beginScan)
    self.scanToggled=True
    self.scanToggler.clicked.connect(self.endScan)
    self.scanToggler.setText('stop scan '+str(self.scanNum))
    
    os.makedirs('scan'+str(self.scanNum)+'/')
    self.taggerFile = open('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'taggerData.csv','a')
    self.taggerFile.write('#updateTime(UTC), #triggerGroupsIntegrated')
    for i in range(self.tofBins):self.taggerFile.write(', #ToF%d'%i)
    self.taggerFile.write('\n')
    self.wmFile = open('scan'+str(self.scanNum)+'/scan'+str(self.scanNum)+'wavemeterData.csv','a')
    self.wmFile.write('#updateTime(UTC), #wmReadout(1/cm)\n')
    self.xToF = list(range(self.tofBins))  # ToF x-axis

    self.freqBins=np.linspace(self.fMinValue, self.fMaxValue, self.fBinsValue+1) #frequency bins
    
    newYray=np.array([self.fMinValue] + list((self.freqBins[:-1]+self.freqBins[1:])/2) + [self.fMaxValue])  # frequency values to plot. Middle of each bin, plus one outer bin on each side in case scan goes outside of expected range.
    print(self.freqBins)
    print(self.yFreq)
    self.lastUpdated, self.lastTaggerData, self.trigGroups=self.pullTaggerData()
    self.tofTotals=np.zeros(self.tofBins)
    print('self.yFreq.shape',self.yFreq.shape)
    print('newYray.shape',newYray.shape)
    self.yFreq = newYray
    self.integrationTimes=np.zeros_like(self.yFreq)
    self.fCounts=np.zeros_like(self.yFreq)
    self.fSignal=np.zeros_like(self.yFreq)
    self.imageTotals=np.zeros((self.tofBins, len(self.yFreq)))
    self.imageData=np.zeros((self.tofBins, len(self.yFreq)))

    if self.deviceCommunication:
      self.device.start_continuous_stream_timestamps_to_file(self.rawDataFile, self.dbName, self.currentRun, binRay=[self.tMinValue,self.tMaxValue,self.tBinsValue],
                                                                    totalToFs_targetFile=self.liveToFs_totals_File, latestToFs_targetFile=self.liveToFs_latest_File, int_time=self.int_time)
    try: self.epicsDriver.start()
    except Exception as e: print('wahhh!',e); self.safeExit(); #exit()
    self.realData = True
    
    '''getting silly for a bit'''
    self.xPositions=np.array([.01,.175,.34])
    self.yPositions=np.array(3*[.795])
    self.xVelocities=np.random.rand(len(self.lineEditList))/100 ; self.yVelocities=np.random.rand(len(self.lineEditList))/100
    #self.xVelocities=np.array([.005,.01,.02]) ; self.yVelocities=2*np.array([.02,.01,.005])
    self.tStep=0
    self.timer.timeout.connect(self.updateEverything)
    self.timer.start()

  def updateEverything(self):
    if not self.scanToggled: print('investigate this!'); quit()
    fCurrent = self.pullFrequency(); self.wmFile.write(str(time.time())+', '+str(fCurrent)+'\n'); self.wmFile.flush()

    #reading ToF data from files, produced from call to start_continuous_stream_timestamps_to_file in beginScan()
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

    lastUpdated, newtaggerData, trigGroups = self.pullTaggerData()
    if lastUpdated != self.lastUpdateTime:
      print('wake up babe, new data just dropped')
      deltaT=trigGroups
      self.taggerFile.write(str(lastUpdated)+', '+str(trigGroups)+', '+str(list(newtaggerData)).strip('[]')+'\n'); self.taggerFile.flush() #TODO: Fix this so that full array is written to file
      self.lastUpdateTime = lastUpdated #now that we've established this was new data, we'll set the latest timestamp as the one we should compare to
      self.tofTotals+=newtaggerData #incrementing aggregate ToF data for scan
      self.updatePlotTof()

      freqBin=np.digitize(fCurrent,self.freqBins)
      self.currentFreqBin=freqBin
      self.integrationTimes[freqBin]+=deltaT
      self.fCounts[freqBin]+=np.sum(newtaggerData) #summing over all ToF bins for counts used in frequency spectrum
      self.fSignal[freqBin] = self.fCounts[freqBin]/self.integrationTimes[freqBin] #bin for countrate is recomputed with new total counts and integration time
      print('test:deltaT=%d,self.fCounts[freqBin]=%d,self.fSignal[freqBin]=%.3f'%(deltaT, self.fCounts[freqBin], self.fSignal[freqBin] ))
      self.updatePlotFreq()
      print('which bin?', freqBin, self.yFreq[freqBin])
      self.imageTotals[:,freqBin]+=newtaggerData
      self.imageData[:,freqBin]=self.imageTotals[:,freqBin]/self.integrationTimes[freqBin]
      self.updateImgPlot()
    else: print("ugh!, tstamp still equals", lastUpdated)
    self.tStep+=1
    #silliness
    self.xPositions+=self.xVelocities; self.yPositions+=self.yVelocities
    for i in range(len(self.xPositions)): #Now checking for wall collisions
      x=self.xPositions[i]; y=self.yPositions[i]
      vx=self.xVelocities[i]; vy=self.yVelocities[i]
      if x<0 or x>.35:
        self.xVelocities[i]*=-1
        if x+vx<0: self.xPositions[i]=0 #in case of clipping into the wall
        if x+vx>1: self.xPositions[i]=1 #in case of clipping into the wall
      if y<.5 or y>.92:
        self.yVelocities[i]*=-1
        if y+vy<0: self.yPositions[i]=0 #in case of clipping into the wall
        if y+vy>1: self.yPositions[i]=1 #in case of clipping into the wall

    buttonWidth=self.fMinLineEdit.size().width()
    buttonHeight=self.fMinLineEdit.size().height()
    for i in range(len(self.xPositions)): #Now for button-button collisions
      '''x1=self.xPositions[i]; y1=self.yPositions[i]
      vx1=self.xVelocities[i]; vy1=self.yVelocities[i]
      for j in range(i+1,len(self.xPositions)):
        if i!=j:
          x2=self.xPositions[j] ; y2=self.yPositions[j]          
          vx2=self.xVelocities[j] ; vy2=self.yVelocities[j]
          rx=x2-x1; ry=y2-y1
          if abs(rx)*self.size().width()<1.12*buttonWidth and abs(ry)*self.size().height()<buttonHeight:
            #print('collision!')
            if abs(abs(rx)*self.size().width()-buttonWidth)<abs(abs(ry)*self.size().height()-buttonHeight):
              print("horizontal collison")
              self.xVelocities[i]=vx2
              self.xVelocities[j]=vx1
              if abs((self.xPositions[i]+vx2)-(self.xPositions[j]+vx1))*self.size().width()<buttonWidth:#self.xPositions[i]<self.xPositions[j]:
                self.xVelocities[i]=vx1
                self.xVelocities[j]=vx2
                print('fudging horizontal positions')
                print(self.xPositions[i],self.xPositions[j],vx1,vx2)

            else:
              print("vertical collison")
              self.yVelocities[i]=vy2
              self.yVelocities[j]=vy1
              if abs((self.yPositions[i])+vy2-(self.yPositions[j]+vy1))*self.size().height()<buttonHeight:
                self.yVelocities[i]=vy1
                self.yVelocities[j]=vy2
                print('fudging vertical positions')
                print(self.yPositions[i],self.yPositions[j],vy1,vy2)'''
    
      self.lineEditList[i].move(int(self.size().width()*self.xPositions[i]), int(self.size().height()*self.yPositions[i]))

  def pullFrequency(self):
    #pulls wavelength measurements from BECOLA4, as long as WSU_sendout.py is running on that PC  
    try:
      # f = np.array(caget('LaserLab:wavenumber_4'))
      freqPV=PV('LaserLab:wavenumber_4'); f=freqPV.get(); freqPV.disconnect()
      print(f)
    except:
      print('womp womp')
      f=-420
    return(f)

  def updatePlotFreq(self):
    if np.all(self.integrationTimes==0):self.data_lineIntegTime.setData(self.integrationTimes, self.yFreq, pen=self.pen2)
    else: self.data_lineIntegTime.setData(-self.integrationTimes*np.max(self.fSignal)/np.max(self.integrationTimes), self.yFreq, pen=self.pen2)
    #else: self.data_lineIntegTime.setData(-self.integrationTimes, self.yFreq, pen=self.pen2)
    if np.all(self.fSignal==0): self.data_lineFreq.setData(self.fSignal, self.yFreq, pen=self.pen1)
    else:
      self.data_lineFreq.setData(self.fSignal, self.yFreq, pen=self.pen1)
      #self.data_lineFreq.setData(self.fSignal/np.max(self.fSignal), self.yFreq, pen=self.pen1)
      self.freqPlotWidget.removeItem(self.data_lineFreqErrors)
      intTimesCopy=np.copy(self.integrationTimes); intTimesCopy[intTimesCopy==0]=.1
      errorSizes=np.sqrt(self.fCounts)/np.max(self.fSignal)/intTimesCopy
      self.data_lineFreqErrors = pg.ErrorBarItem(x=self.fSignal, y=np.array(self.yFreq), left=errorSizes, right=errorSizes, pen=self.pen4)
      #self.data_lineFreqErrors = pg.ErrorBarItem(x=self.fSignal/np.max(self.fSignal), y=np.array(self.yFreq), left=errorSizes, right=errorSizes, pen=self.pen1)
      self.freqPlotWidget.addItem(self.data_lineFreqErrors)
    self.currentFreqPoint.setData([self.fSignal[self.currentFreqBin]], [self.yFreq[self.currentFreqBin]],
                                                      pen=None, symbol='o', symbolPen=pg.mkPen(color=(0, 255, 0), width=1), symbolBrush=pg.mkBrush(0, 0, 255, 255), symbolSize=7)
    self.currentIntegPoint.setData([-self.integrationTimes[self.currentFreqBin]*np.max(self.fSignal)/np.max(self.integrationTimes)], [self.yFreq[self.currentFreqBin]],
                                                      pen=None, symbol='o', symbolPen=pg.mkPen(color=(0, 255, 0), width=5), symbolBrush=pg.mkBrush(0, 0, 255, 255), symbolSize=5)
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
  window.resize(1300,1300)
  app.aboutToQuit.connect(window.safeExit) #TODO: write safeExit function
  window.show()
  sys.exit(app.exec_())