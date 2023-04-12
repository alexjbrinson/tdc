import numpy as np 
from S15lib.instrumentsBrinson import TimeStampTDC1
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import TDCutilities as tdcu

import sqlite3 as sl
import pandas as pd

dev = TimeStampTDC1('COM3')
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
dic = dev.read_timestamps_from_file_as_dict(fname='newdb2.raw')
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

plt.hist(dframe2.tStamp, bins=1000)
plt.show()