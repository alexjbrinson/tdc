import numpy as np 
from tdcClass import TimeStampTDC1
import time
import pandas as pd
import matplotlib.pyplot as plt
import TDCutilities as tdcu
import sqlite3 as sl
import pandas as pd
import pickle

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
        #print(bytes_hex)
        ts_word_list = [
            int(bytes_hex[i : i + 8], 16) for i in range(0, len(bytes_hex), 8)
        ][::-1]
        print(ts_word_list)
        plt.plot([t>>5 for t in ts_word_list], label='[t>>5 for t in ts_word_list]')

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
        plt.plot(ts_list, label='ts_list')
        timingArray=[]
        for i in range(10):
          t1=time.time()
          ts_list2 = np.array(ts_list, dtype='int64') * 2   #this method takes this long: 0.0009999275207519531
          #ts_list2 = np.array([t*2 for t in ts_list])      #this method takes this long: 0.0019996166229248047
          t2=time.time()
          timingArray+=[t2-t1]
        print("this method takes this long:", np.mean(timingArray))
        plt.plot(np.array(ts_list) * 2, label='np.array(ts_list) * 2')
        plt.plot(ts_list2, label="np.array(ts_list, dtype='int64') * 2")
        event_channel_list = event_channel_list
        plt.hlines(2**31, 0, len(ts_word_list),'black', label=r'$2^{31}$')
        print(np.array(ts_list).dtype)
        plt.legend()
        plt.show()
        return ts_list2, event_channel_list

rawDataFile='currentData.raw'
dbname='testdb.db'
run=-1
liveDataFile = "iTurnedMyselfIntoAPickle.pkl"

with open(rawDataFile, "rb") as f: lines = f.read(); f.close()

bah=read_timestamps_bin(lines)
print(bah[0])

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