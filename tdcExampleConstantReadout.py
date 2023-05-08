import numpy as np 
from tdcClass import TimeStampTDC1
import time
import pandas as pd
import matplotlib.pyplot as plt
import TDCutilities as tdcu
import sqlite3 as sl
import pandas as pd
import pickle

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
dbname='allData.db'
run=9
liveDataFile = "iTurnedMyselfIntoAPickle.pkl"

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
dframe=pd.read_sql_query("SELECT * from TDC", con)# WHERE run="+str(run)+" AND channel ="+str(2), con)
t1=time.time()
print(dframe)
quit()
#plt.hist(dframe.tStamp, bins=1000)
print('time to load parsed database:', t1-t0)

print(time.time())

#plt.plot(dev.allTriggers)
dic = tdcu.read_timestamps_from_file_as_dict(fname=rawDataFile)
plt.plot(dic["channel 1"])


with open(liveDataFile,'rb') as file:
  resultFromLiveBinning=pickle.load(file)
  file.close()
t2=time.time()
print("time to load pickle:",t2-t1)


#plt.plot(resultFromLiveBinning['channel 2'])
plt.show()
#320364612
#171934980