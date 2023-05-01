import sqlite3 as sl
import numpy as np 
from S15lib.instrumentsBrinson import TimeStampTDC1
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import os
import multiprocessing
import threading
import serial

def writeToDB(connection, runNum):
  #emulates the data format that I'm using to store actual TDC data, but this is just random data
  runningCondition=True
  while runningCondition:
    period=0.1
    time.sleep(period)
    bufferDataTrigger=time.time()
    eventData=bufferDataTrigger+np.sort(period*np.random.rand(np.random.randint(50)))
    xData = np.concatenate([[bufferDataTrigger], eventData]); xData=[float(x) for x in xData]
    yData = np.concatenate([[1], 2*np.ones_like(eventData)]); yData=[int(y) for y in yData]
    zData = [int(runNum) for i in range(len(xData))]
    data=list(zip(xData,yData, zData))
    sql = 'INSERT OR IGNORE INTO TDC (tStamp, channel, run) values(?, ?, ?)'
    connection.executemany(sql,data)
    connection.commit()
    runningCondition=False

def writeToDB2(connection, runNum):
  #emulates the data format that I'm using to store actual TDC data, but this is just random data
  runningCondition=True
  while runningCondition:
    period=0.1
    time.sleep(period)
    bufferDataTrigger=time.time()
    eventData=bufferDataTrigger+period*np.linspace(0, 1, 10)
    xData = np.concatenate([[bufferDataTrigger], eventData]); xData=[float(x) for x in xData]
    yData = np.concatenate([[1], 2*np.ones_like(eventData)]); yData=[int(y) for y in yData]
    zData = [int(runNum) for i in range(len(xData))]
    data=list(zip(xData,yData, zData))
    sql = 'INSERT OR IGNORE INTO TDC (tStamp, channel, run) values(?, ?, ?)'
    connection.executemany(sql,data)
    connection.commit()
    runningCondition=False

def readAndParseScan(dframe, dropEnd=True, triggerChannel=1):
  #from dataframe of (timestamps,channel,run) data, converts to relative times from trigger signal
  triggerTimes=np.array(dframe[dframe.channel==triggerChannel].tStamp)
  try: firstTriggerTime=triggerTimes[0]; lastTriggerTime=triggerTimes[-1]; #print('success?',triggerTimes)
  except: print('whauua?', triggerTimes);# quit()
  dframe.tStamp=dframe.tStamp.map(lambda v : v if v>=firstTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the beginning of my data batch
  if dropEnd:
    dframe.tStamp=dframe.tStamp.map(lambda v : v if v<lastTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the end of my data batch
  else: triggerTimes=np.append(triggerTimes, np.max(dframe.tStamp)+1) #if we don't drop the end, I need to add a final artificial trigger time which is later than all other timestamps, just so the for loop below will run as intended.
  allChannels=np.unique(dframe.channel); print('test:', allChannels)
  eventChannels = allChannels[allChannels!=triggerChannel]; print('test2:', eventChannels)
  nf=pd.DataFrame()
  for i in range(len(triggerTimes)-1):
    for eventChannel in eventChannels:
      events=(dframe[np.array(dframe.channel==eventChannel)&np.array(dframe.tStamp>triggerTimes[i]) & np.array(dframe.tStamp<triggerTimes[i+1])]).copy()
      events.tStamp-=triggerTimes[i]
      nf=nf.append(events)
  return(nf)
'''
def readAndParseScan2(dframe, dropEnd=True, triggerChannel=1):
  #from dataframe of (timestamps,channel,run) data, converts to relative times from trigger signal
  triggerTimes=np.array(dframe[dframe.channel==triggerChannel].tStamp)
  try: firstTriggerTime=triggerTimes[0]; lastTriggerTime=triggerTimes[-1]; #print('success?',triggerTimes)
  except: print('whauua?', triggerTimes);# quit()
  dframe.tStamp=dframe.tStamp.map(lambda v : v if v>=firstTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the beginning of my data batch
  if dropEnd:
    dframe.tStamp=dframe.tStamp.map(lambda v : v if v<lastTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the end of my data batch
  else: triggerTimes=np.append(triggerTimes, np.max(dframe.tStamp)+1) #if we don't drop the end, I need to add a final artificial trigger time which is later than all other timestamps, just so the for loop below will run as intended.
  allChannels=np.unique(dframe.channel); print('test:', allChannels)
  eventChannels = allChannels[allChannels!=triggerChannel]; print('test2:', eventChannels)
  nf=pd.DataFrame()
  for eventChannel in eventChannels:
    for i in range(len(triggerTimes)-1):
      eventTime=
      events=(dframe[np.array(dframe.channel==eventChannel)&np.array(dframe.tStamp>triggerTimes[i]) & np.array(dframe.tStamp<triggerTimes[i+1])]).copy()
      events.tStamp-=triggerTimes[i]
      nf=nf.append(events)
  return(nf)
'''
if __name__ == "__main__":
  con= sl.connect('dummy.db')
  with con:
          con.execute("""
          CREATE TABLE IF NOT EXISTS TDC (
              tStamp FLOAT(25) NOT NULL PRIMARY KEY,
              channel INTEGER,
              run INTEGER
          );
          """)

  #generating dummy data
  for runNum in range(20):
    writeToDB2(con, runNum)

  #loading database one run at a time
  totalFrame = pd.DataFrame()
  for runNum in range(20):
    tempFrame= pd.read_sql_query("SELECT * from TDC WHERE run == "+str(runNum), con)
    totalFrame=totalFrame.append(readAndParseScan(tempFrame, dropEnd=False))
  #plt.hist(totalFrame.tStamp,bins=20)
  print(len(totalFrame))
  heights, bins = np.histogram(totalFrame.tStamp, bins=200)
  plt.plot((bins[1:]+bins[:-1])/2, heights)
  t0=time.time()
  #and now the whole database all at once, for comparison
  tempFrame= pd.read_sql_query("SELECT * from TDC", con)
  t1=time.time()
  totalFrame2=readAndParseScan(tempFrame, dropEnd=False)
  t2=time.time()
  print(len(totalFrame2))
  heights2, bins2 = np.histogram(totalFrame2.tStamp, bins=200)
  plt.plot((bins2[1:]+bins2[:-1])/2, heights2)
  t3=time.time()
  print(t1-t0)
  print(t2-t1)
  print(t3-t2)
  plt.show()