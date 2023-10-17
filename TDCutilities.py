import sqlite3 as sl
import numpy as np 
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import os
import multiprocessing
import threading
import serial
from numba import njit

def channel_to_binString(channel):
  #pretty silly, but effective
  if   channel==1: return('0001')
  elif channel==2: return('0010')
  elif channel==3: return('0100')
  elif channel==4: return('1000')
  else: return(-1)

#@njit #why does this break when I call it from the histogram method in tdcClass.py? #TODO: investigate?
def timeStampConverter(triggerTimes, eventTimes):
  triggerTimes=np.append(triggerTimes,1+eventTimes[-1]) #adding a fake trigger that occurs after last event, just so I don't run out bounds on my index
  i=0; stopIndex=0; goodTimeStamps=[1.]; triggerGroups=[0]
  for j in range(len(eventTimes)):
    if eventTimes[j]>triggerTimes[i+1]:
      startIndex = stopIndex
      stopIndex = j
      goodTimeStamps+=list(eventTimes[startIndex:stopIndex]-triggerTimes[i])
      triggerGroups+=[i]*(stopIndex-startIndex)
      while eventTimes[j]>triggerTimes[i+1]:
        i+=1 #in case there are multiple triggers between events for some reason...
  #since the last trigger group is (by construction) before the final trigger time, it won't be appended by my if condition. Need to do it manually here:
  goodTimeStamps+=list(eventTimes[stopIndex:]-triggerTimes[i])
  triggerGroups+=[i]*(len(eventTimes)-stopIndex)
  return(goodTimeStamps[1:], triggerGroups[1:])

def readAndParseScan(dic, dropEnd=True, triggerChannel=1, run=-1, t0=0):
  triggerTimes=np.array(dic['channel '+str(triggerChannel)])
  try: firstTriggerTime=triggerTimes[0]; lastTriggerTime=triggerTimes[-1]; #print('success?',triggerTimes)
  except: print('whauua?', triggerTimes);# quit()
  nf=pd.DataFrame()
  for key in dic.keys():
    i = int(key.strip('channel '))
    if i == triggerChannel: pass
    elif len(dic[key])>0:
      eventTimes=np.array(dic[key])
      eventTimes=eventTimes[eventTimes>=firstTriggerTime] #dropping data before first trigger #TODO: do this in timeStampConverter() without slicing
      if dropEnd:eventTimes=eventTimes[eventTimes<lastTriggerTime]
      goodTimeStamps, triggerGroups=timeStampConverter(triggerTimes, eventTimes)
      nf=pd.concat([nf,pd.DataFrame({'tStamp':goodTimeStamps, 'channel':i*np.ones_like(goodTimeStamps,dtype=int),
       'run':run*np.ones_like(goodTimeStamps,dtype=int),'triggerGroup':triggerGroups, 'globalTime':t0+(eventTimes*1E-9)})])
  return(nf)

'''def readAndParseScan(dframe, dropEnd=True, triggerChannel=1):
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
    eventTimes=np.array(dframe[np.array(dframe.channel==eventChannel)].tStamp)
    #triggerTimes=np.append(triggerTimes,1+np.max(eventTimes)) #adding a fake trigger that occurs after last event, just so I don't run out bounds on my index
    goodTimeStamps=timeStampConverter(triggerTimes, eventTimes)
    nf=pd.DataFrame({'tStamp':goodTimeStamps})
  return(nf)'''

def channel_to_pattern(channel):
    return int(2 ** (channel - 1))

def read_timestamps_bin(binary_stream):
        """
        Reads the timestamps accumulated in a binary sequence
        Returns:
            Tuple[List[float], List[str]]:
                Returns the event times in ns and the corresponding event channel.
                The channel are returned as string where a 1 indicates the
                trigger channel.
                For example an event in channel 2 would correspond to "0010".
                Two coinciding events in channel 3 and 4 correspond to "1100"
        """
        bytes_hex = binary_stream[::-1].hex()
        ts_word_list = [
            int(bytes_hex[i : i + 8], 16) for i in range(0, len(bytes_hex), 8)
        ][::-1]

        ts_list = []
        event_channel_list = []
        periode_count = 0
        periode_duration = 1 << 27
        prev_ts = -1
        for ts_word in ts_word_list:
            time_stamp = ts_word >> 5
            pattern = ts_word & 0x1F
            if prev_ts != -1 and time_stamp < prev_ts:
                periode_count += 1
            #         print(periode_count)
            prev_ts = time_stamp
            if (pattern & 0x10) == 0:
                ts_list.append(time_stamp + periode_duration * periode_count)
                event_channel_list.append("{0:04b}".format(pattern & 0xF))

        ts_list2 = np.array(ts_list, dtype='int64') * 2
        event_channel_list = np.array(event_channel_list)
        return ts_list2, event_channel_list

def read_timestamps_from_file(fname=None):
  """
  Reads the timestamps accumulated in a binary file
  """
  if fname==None: return()
  with open(fname, "rb") as f:
      lines = f.read()
  f.close()
  return read_timestamps_bin(lines)

def read_timestamps_from_file_as_dict(fname=None):
  """
  Reads the timestamps accumulated in a binary file
  Returns dictionary where timestamps['channel i'] is the timestamp array
  in nsec for the ith channel
  """
  if fname==None: return()
  timestamps = {}
  (times, channels,) = (read_timestamps_from_file(fname=fname))  # channels may involve coincidence signatures such as '0101'
  for channel in range(1, 5, 1): timestamps["channel {}".format(channel)] = list(times[channels==channel_to_binString(channel)])
  return timestamps

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

  #loading database one run at a time
  totalFrame = pd.DataFrame()
  for runNum in range(20):
    tempFrame= pd.read_sql_query("SELECT * from TDC WHERE run == "+str(runNum), con)
    totalFrame=totalFrame.append(readAndParseScan(tempFrame, dropEnd=False))
  #plt.hist(totalFrame.tStamp,bins=20)
  print(len(totalFrame))
  print(totalFrame)
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