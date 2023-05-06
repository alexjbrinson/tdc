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

con= sl.connect('dummy.db')
with con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS TDC (
            tStamp FLOAT(25) NOT NULL PRIMARY KEY,
            channel INTEGER,
            scan INTEGER
        );
        """)

def writeToDB(connection, scanNum):
  runningCondition=True
  while runningCondition:
    period=0.1
    time.sleep(period)
    bufferDataTrigger=time.time()
    eventData=bufferDataTrigger+np.sort(period*np.random.rand(np.random.randint(50)))
    xData = np.concatenate([[bufferDataTrigger], eventData]); xData=[float(x) for x in xData]
    yData = np.concatenate([[1], 2*np.ones_like(eventData)]); yData=[int(y) for y in yData]
    zData = [int(scanNum) for i in range(len(xData))]
    data=list(zip(xData,yData, zData))
    sql = 'INSERT OR IGNORE INTO TDC (tStamp, channel, scan) values(?, ?, ?)'
    connection.executemany(sql,data)
    connection.commit()
    runningCondition=False

# for scanNum in range(20):
#   writeToDB(con, scanNum)

def readAndParseScan(connection, scanNum=-1, dropEnd=True):
  #from already established database connection, loads dataframe from just one scan number, then converts time stamps/channels to relative times from trigger signal
  if scanNum==-1: dframe = pd.read_sql_query("SELECT * from TDC", connection)
  else: dframe = pd.read_sql_query("SELECT * from TDC WHERE scan == "+str(scanNum), connection)
  triggerTimes=np.array(dframe[dframe.channel==1].tStamp)
  firstTriggerTime=triggerTimes[0]; lastTriggerTime=triggerTimes[-1]
  dframe.tStamp=dframe.tStamp.map(lambda v : v if v>=firstTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the beginning of my data batch
  if dropEnd:
    dframe.tStamp=dframe.tStamp.map(lambda v : v if v<lastTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the end of my data batch
  else: triggerTimes=np.append(triggerTimes, np.max(dframe.tStamp)+1) #if we don't drop the end, I need to add a final artificial trigger time which is later than all other timestamps, just so the for loop below will run as intended.

  nf=pd.DataFrame()
  for i in range(len(triggerTimes)-1):
    events=(dframe[np.array(dframe.channel==2)&np.array(dframe.tStamp>triggerTimes[i]) & np.array(dframe.tStamp<triggerTimes[i+1])]).copy()
    events.tStamp-=triggerTimes[i]
    nf=nf.append(events)
  return(nf)

totalFrame = pd.DataFrame()
for scanNum in range(20):
  totalFrame=totalFrame.append(readAndParseScan(con, scanNum=scanNum, dropEnd=False))
#plt.hist(totalFrame.tStamp,bins=20)
print(len(totalFrame))
heights, bins = np.histogram(totalFrame.tStamp, bins=20)
plt.plot((bins[1:]+bins[:-1])/2, heights)
t0=time.time()
totalFrame2=readAndParseScan(con, scanNum=-1, dropEnd=False)
print(len(totalFrame2))
heights2, bins2 = np.histogram(totalFrame2.tStamp, bins=20)
plt.plot((bins2[1:]+bins2[:-1])/2, heights2)
t1=time.time()
print(t1-t0)
plt.show()