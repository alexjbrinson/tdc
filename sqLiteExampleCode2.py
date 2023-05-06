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

dframe = pd.read_sql_query("SELECT * from TDC", con); print(dframe)
triggerTimes=np.array(dframe[dframe.channel==1].tStamp)
firstTriggerTime=triggerTimes[0]; lastTriggerTime=triggerTimes[-1]
dframe.tStamp=dframe.tStamp.map(lambda v : v if v>=firstTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the beginning of my data batch
dframe.tStamp=dframe.tStamp.map(lambda v : v if v<lastTriggerTime else float('NaN')); dframe.dropna(inplace=True) #this is how I'll avoid partial ToF spectra at the end of my data batch

eventTimes=np.array(dframe[dframe.channel==2].tStamp)
nf=pd.DataFrame()
for i in range(len(triggerTimes)-1):
    events=(dframe[np.array(dframe.channel==2)&np.array(dframe.tStamp>triggerTimes[i]) & np.array(dframe.tStamp<triggerTimes[i+1])]).copy()
    events.tStamp-=triggerTimes[i]
    nf=nf.append(events)

print(nf)
plt.hist(nf.tStamp,bins=20)
plt.show()

