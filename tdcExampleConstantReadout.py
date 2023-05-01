import numpy as np 
from S15lib.instrumentsBrinson import TimeStampTDC1
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import TDCutilities as tdcu

import sqlite3 as sl
import pandas as pd

#dev = TimeStampTDC1('COM3')
# print('successful connection to TDC device')
# dev.level = dev.TTL_LEVELS #use ts.NIM_LEVELS for nim signals

# dev.start_continuous_stream_timestamps_to_database('newdb2.db', 0)
# for i in range(10):
#   print('sleeping',i)
#   time.sleep(.5)
# dev.stop_continuous_stream_timestamps_to_database()
'''
con= sl.connect('newdb2.db')
dframe=pd.read_sql_query("SELECT * from TDC", con)
print(np.unique(dframe.channel))
ch1Times=np.array(dframe[dframe.channel==1].tStamp)
ch2Times=np.array(dframe[dframe.channel==2].tStamp)

print(ch1Times[1:]-ch1Times[:-1])#[1751004 2000098 2000098 ... 2000098 2000098 2000098]
print(ch2Times[1:]-ch2Times[:-1])#[100004 100006 100004 ... 100004 100004 100004]

plt.plot(dframe.tStamp,'b.', label='channel 1')
plt.xlabel('i'); plt.ylabel('tStamp')
plt.title('What is going on?? Pt1')
plt.show()

#plt.hist(ch1Times[1:]-ch1Times[:-1],bins=100)
plt.plot(ch1Times[1:]-ch1Times[:-1],'b.')
plt.xlabel('i'); plt.ylabel('t1[i+1]-t1[i]')
plt.title('What is going on?? Pt2')
plt.show()

plt.hist(ch1Times[1:]-ch1Times[:-1],bins=100)
plt.xlabel('t1[i+1]-t1[i]'); plt.ylabel('counts')
plt.title('What is going on?? Pt3')
plt.show()

dframe = tdcu.readAndParseScan(con, runNum=0, dropEnd=True, triggerChannel=1)
print(dframe)
x=dframe.tStamp
print(np.min(x),np.max(x))
#plt.plot(x, np.ones_like(x),'b.')
heights, bins = np.histogram(dframe.tStamp, bins=2000)
plt.plot((bins[1:]+bins[:-1])/2, heights)
plt.title('this is bad and I feel bad')
plt.show()

quit()
'''

'''
# dev.start_continuous_stream_timestamps_to_file('newdb2.raw')
# for i in range(10):
#   print('sleeping',i)
#   time.sleep(1)
#   #dic=dev.read_timestamps_from_file_as_dict()
# dev.stop_continuous_stream_timestamps_to_file()
'''
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

        ts_list = np.array(ts_list) * 2
        event_channel_list = event_channel_list
        return ts_list, event_channel_list

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

dic = read_timestamps_from_file_as_dict(fname='newdb2.raw')
ch1Times=np.array(dic['channel 1'])
ch2Times=np.array(dic['channel 2'])
ch1Entries=[[t1, 1] for t1 in ch1Times]
ch2Entries=[[t2, 2] for t2 in ch2Times]
dframe=pd.DataFrame(np.vstack([ch1Entries,ch2Entries]), columns=['tStamp','channel'])
print(dframe)

t0=time.time()
dframe2 = tdcu.readAndParseScan(dframe, dropEnd=True, triggerChannel=1)
t1=time.time()
print(dframe2)
print("time elapsed:", t1-t0) #time elapsed: 11.502874851226807 , 1.4951014518737793, 2.0678484439849854

plt.hist(dframe2.tStamp, bins=1000)
plt.show()