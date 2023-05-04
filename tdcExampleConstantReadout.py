import numpy as np 
from tdcClass import TimeStampTDC1
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import TDCutilities as tdcu
import sqlite3 as sl
import pandas as pd



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
#plt.hist(dframe.tStamp, bins=1000)
#plt.show()

'''
rawDataFile='currentData.raw'
dbname='newdb3.db'
run=0

#Collect data with this stuff
# dev = TimeStampTDC1('COM3')
# print('successful connection to TDC device')
# dev.level = dev.TTL_LEVELS #use ts.NIM_LEVELS for nim signals
# dev.start_continuous_stream_timestamps_to_file(rawDataFile, dbname, run)
# for i in range(10):
#   print('sleeping',i)
#   time.sleep(5)#(.5)
# dev.stop_continuous_stream_timestamps_to_file()

t0=time.time()
con=sl.connect(dbname)
# dframe=pd.read_sql_query("SELECT * from TDC", con)
dframe=pd.read_sql_query("SELECT * from TDC WHERE run="+str(run), con)
t1=time.time()
print(dframe)
plt.hist(dframe.tStamp, bins=1000)
print('time to load parsed database:', t1-t0)
plt.show()'''