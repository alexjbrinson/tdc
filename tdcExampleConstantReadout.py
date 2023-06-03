import numpy as np 
from tdcClass import TimeStampTDC1
import time
import pandas as pd
import matplotlib.pyplot as plt
import TDCutilities as tdcu
import sqlite3 as sl
import pandas as pd
import pickle


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
        counter=0
        bytes_hex = binary_stream[::-1].hex()
        ts_word_list = [
            int(bytes_hex[i : i + 8], 16) for i in range(0, len(bytes_hex), 8)
        ][::-1]
        ts_word_list_reduced=[ts_word_list[i] for i in [111871,111872,111873]]; print(ts_word_list_reduced)
        ts_list = []
        event_channel_list = []
        periode_count = 0
        periode_duration = 1 << 27
        prev_ts = -1
        plt.plot(ts_word_list)
        plt.plot(np.array(ts_word_list)>>5)
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
                #plt.plot(counter,ts_list[-1]); counter+=1
        #plt.plot(ts_list)
        
        ts_list2 = np.array(ts_list, dtype='int64') * 2
        plt.plot(ts_list2)
        event_channel_list = event_channel_list
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
  for channel in range(1, 5, 1):  # iterate through channel numbers 1, 2, 3, 4
      timestamps["channel {}".format(channel)] = times[
          [int(ch, 2) & channel_to_pattern(channel) != 0 for ch in channels]
      ]
  return timestamps
'''
t0=time.time()
dic = tdcu.read_timestamps_from_file_as_dict(fname='newdb2.raw')
t1=time.time()
dframe = tdcu.readAndParseScan(dic, dropEnd=True, triggerChannel=1)
t2=time.time()
dframe2 = tdcu.readAndParseScan(dic, dropEnd=True, triggerChannel=1)
t3=time.time()
print(dframe2)
print("time elapsed on file load:", t1-t0) #time elapsed: 11.502874851226807 , 1.4951014518737793, 2.0678484439849854
print("time elapsed the first function call:", t2-t1)
print("time elapsed the second function call:", t3-t2)
plt.hist(dframe.tStamp, bins=1000)
plt.show()'''


rawDataFile='currentData.raw'
dbname='fastData.db'
run=0
liveDataFile = "iTurnedMyselfIntoAPickle.pkl"

dic = read_timestamps_from_file_as_dict(fname=rawDataFile)
triggerTimes=np.array(dic['channel 1'])
eventTimes=np.array(dic['channel 3'])
#plt.plot(eventTimes,'.')
plt.show()
'''dic = tdcu.read_timestamps_from_file_as_dict(fname=rawDataFile)
print(dic)
triggerTimes=np.array(dic['channel 1'])
firstTriggerTime=triggerTimes[0]; lastTriggerTime=triggerTimes[-1]
eventTimes=np.array(dic['channel 2'])
eventTimes=eventTimes[eventTimes>=firstTriggerTime]
plt.plot(triggerTimes)
#plt.plot(eventTimes)
plt.show()
cleanFrame=tdcu.readAndParseScan(dic, dropEnd=True, triggerChannel=1, run=-1, t0=0)'''

#Collect data with this stuff
# dev = TimeStampTDC1('COM3')
# print('successful connection to TDC device')
# dev.level = dev.TTL_LEVELS #use ts.NIM_LEVELS for nim signals
# dev.clock='2'#force internal clock
# time.sleep(1)
# dev.start_continuous_stream_timestamps_to_file(rawDataFile, dbname, run, binRay=[0,2.5E6,10000], pickleDic=liveDataFile)
# for i in range(10):
#   print('sleeping',i)
#   time.sleep(.5)#(.5)
# dev.stop_continuous_stream_timestamps_to_file()

t0=time.time()
con=sl.connect(dbname)
dframe=pd.read_sql_query("SELECT * from TDC WHERE run="+str(run)+" AND channel ="+str(3), con)
t1=time.time()
print(dframe)

#plt.hist(dframe.tStamp, bins=1000);plt.title(dbname);plt.xlabel('tStamp'); plt.ylabel('counts');
plt.plot(dframe.tStamp,'b.');plt.title(dbname);plt.ylabel('tStamp'); plt.xlabel('index');


#plt.plot(dev.allTriggers)
#dic = tdcu.read_timestamps_from_file_as_dict(fname=rawDataFile)
#plt.plot(dic["channel 1"])

t2=time.time()
with open(liveDataFile,'rb') as file:
  resultFromLiveBinning=pickle.load(file)
  file.close()
t3=time.time()
print('time to load parsed database:', t1-t0)
print("time to load pickle:",t3-t2)
#plt.plot(resultFromLiveBinning['channel 2'])
n1=len(dframe.tStamp)
n2=np.sum(resultFromLiveBinning['channel 3'])
print('total registered counts from full database',n1)
print('total registered counts from live binning=',n2)
print('captured event ratio = ',n2/n1)
plt.show()
#320364612
#171934980