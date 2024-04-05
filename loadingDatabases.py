import sqlite3 as sl
import sys, os
import time
import numpy as np
import pandas as pd
import math
from datetime import datetime
import pickle
import matplotlib.pyplot as plt

# def getHistCurve(run, bins=np.linspace(0, 1E5, 101)):
#   try:
#     dataDirectory='../data/RFQ Tests/'
#     dbFile=dataDirectory+'scan%d/scan%d_allData.db'%(run,run)
#     connection=sl.connect(dbFile)
#     runFrame=pd.read_sql_query("SELECT * from TDC WHERE run="+str(run), connection); print(runFrame)
#     #totalTriggers=np.max(np.array(runFrame.triggerGroup))
#     totalTriggers=len(np.unique(runFrame.triggerGroup))
#     totalTimestamps= len(runFrame.tStamp)
#     print('totalTriggers=%d'%totalTriggers)
#     yToF, dumbBins =np.histogram(np.array(runFrame.tStamp), bins=bins)
#     yToF=yToF/float(totalTriggers) #normalizing histogram heights by total number of bunches
#     return(yToF/np.max(yToF),totalTimestamps)
#     #plt.plot((bins[1:]+bins[:-1])/2,yToF, label='run%d'%run)
#   except: return(False)

def generateTimeStream(run, bins=np.linspace(0, 1E5, 101)):
  try:
    dataDirectory='../data/RFQ Tests/'
    dbFile=dataDirectory+'scan%d/scan%d_allData.db'%(run,run)
    connection=sl.connect(dbFile)
    runFrame=pd.read_sql_query("SELECT * from TDC WHERE run="+str(run), connection); #print(runFrame)
    #totalTriggers=len(np.unique(runFrame.triggerGroup))
     #group dataframe by trigger group (probably use pd.groupby() )
     #count the number of elements in each group
     #return (trigger group # vs. count)
    totalTimestamps= len(runFrame.tStamp)
    grouped_data = runFrame.groupby('triggerGroup').count().reset_index('triggerGroup')
    Trigger_group = np.array(grouped_data['triggerGroup'])
    Counts = np.array(grouped_data['index'])
    print(grouped_data)
    return(Trigger_group, Counts)
  except: return(False)

#generateTimeStream(121)
#quit() 

labelDict={
  
 254:'x', 
 # 208:'p',
 # 207:'l',
 # 206:'i',
 # 205:'s',
 # 204:'w',
 #203:'d', 
}  

ave_count = []
count_error = []

bins=np.linspace(0, 1E5, 101)
print('wo',len(bins))
for i in labelDict.keys():
  print(i)
  label=labelDict[i]
  # (yData, N)=getHistCurve(i,bins=bins)
  # print( np.mean(yData))
  (grouped_x, grouped_y)=generateTimeStream(i,bins=bins)
  # a, bins = np.histogram(grouped_y, bins = 500)
  # ave_count.append(np.mean(grouped_y))
  # count_error.append(np.std(grouped_y))
  o = (bins[1:]+bins[:-1])/2
  # try:plt.plot(o,yData, label=label)
  try:plt.plot(grouped_x,grouped_y)
  #plt.plot((bins[1:]+bins[:-1])/2, a)
  except: pass


#Width_err = 12.3 /np.sqrt(N)
# print('error is',Width_err)

# FWHM = 2*np.sqrt(2*np.log(2))*np.array(count_error)
# Width_error = FWHM/np.sqrt(N)
# Loading_time = [5,10,20,30,50,80,100]
# plt.errorbar(Loading_time, FWHM, yerr=Width_error, fmt='o', capsize=5, label = '0.5 sccm\n30 ms storage time')

plt.legend()
plt.title('Time of Flight')
#plt.xlabel('Time (ns)')
plt.xlabel('Loading Time ($\\mu$s) ')
plt.ylabel('Count rate (cps)') 
# ■plt.xlim(0,10000)
plt.show()
