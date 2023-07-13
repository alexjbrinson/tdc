import numpy as np 
import time
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3 as sl

def analyzeRun(run, minToF, maxToF):
  dframe=pd.read_sql_query("SELECT * from TDC WHERE run="+str(run)+" AND channel ="+str(3)+" AND tStamp > "+str(minToF)+" AND tStamp < "+str(maxToF), con)
  countsByTrigger=dframe.groupby(['triggerGroup'])['run'].size()
  nonEmptyTriggers=list(countsByTrigger.keys())
  finalTrigger=nonEmptyTriggers[-1]
  countsRay=np.zeros(finalTrigger+1)
  for trigGroup in nonEmptyTriggers: countsRay[trigGroup]=countsByTrigger[trigGroup]
  return(dframe, countsRay)

dbname='29Jun2023Data.db'; con=sl.connect(dbname)
minToF, maxToF = 5000, 6000
bins=np.linspace(minToF, maxToF,101)
runs=[27, 28, 29, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 47]
frequencies=[12546.695, 12546.75, 12546.8, 12546.9, 12547.0, 12547.1, 12547.2, 12547.3, 12547.4, 12547.5, 12547.6, 12547.7, 12547.8, 12547.915, 12548.015]

spectroscopyFrame=pd.DataFrame(frequencies, index=runs, columns=['freq'])
spectroscopyFrame['countRate']=-1.; spectroscopyFrame['error']=-1.

mosaicLabels=[ ['Run %d - timestream'%run for run in runs] , ['Run %d - ToF'%run for run in runs], ['spectrum' for run in runs]]
print(mosaicLabels)

t0=time.time()
fig, axs = plt.subplot_mosaic(mosaicLabels, figsize=(18, 10),gridspec_kw={'height_ratios': [1, 2, 4]})
j=0
for run in runs[:]:
  print('run %d'%run)
  dframe, countsRay=analyzeRun(run, minToF, maxToF)
  #fig, axs = plt.subplots(2, len(runs), figsize=(10, 10), num='Run %d'%run)
  ax0=axs[mosaicLabels[0][j]]; ax1=axs[mosaicLabels[1][j]]
  ax0.sharey(axs[mosaicLabels[0][0]])
  ax1.sharey(axs[mosaicLabels[1][0]])
  ax0.plot(countsRay,'b'); ax0.set_title('Run %d'%run)
  heights,bins=np.histogram(dframe.tStamp, bins=bins)
  #axs[1,j].hist(dframe.tStamp, bins=bins)
  ax1.plot((bins[1:]+bins[:-1])/2,heights/len(countsRay))
  if j==0:
    ax0.set_ylabel('Timestreams\ncounts')
    ax1.set_ylabel('ToF Histograms\ncounts/triggers')
    text1 = fig.text(0.905, 0.77, 'Trigger\ngroup')
    text2 = fig.text(0.905, 0.535, 'ToF (ns)') 
  else: 
    ax0.get_yaxis().set_visible(False); ax1.get_yaxis().set_visible(False);
    ax0.get_xaxis().set_visible(False);ax1.get_xaxis().set_visible(False)
    ax0.sharey(axs[mosaicLabels[0][0]]); ax0.sharex(axs[mosaicLabels[0][0]])
    ax1.sharey(axs[mosaicLabels[1][0]])

  print('mean=%.3f, std=%.3f'%(np.mean(countsRay), np.std(countsRay) ) )
  print('sum of countsRay=',np.sum(countsRay))
  print('size of dframe =', dframe.shape)
  print('rate=%.3f, +- %.3f'%(np.sum(countsRay)/len(countsRay) , np.sqrt(np.sum(countsRay))/len(countsRay) ) )
  spectroscopyFrame['countRate'][run]=np.sum(countsRay)/len(countsRay)
  spectroscopyFrame['error'][run]=np.std(countsRay)/np.sqrt(len(countsRay))#np.sqrt(np.sum(countsRay))/len(countsRay)
  j+=1
t1=time.time()
print(t1-t0)
print(spectroscopyFrame)
finAx=axs['spectrum']
finAx.errorbar(spectroscopyFrame['freq'],spectroscopyFrame['countRate'],yerr=spectroscopyFrame['error'])
finAx.set_ylabel('counts per trigger'); finAx.set_title('Frequency Spectrum')
text3=fig.text(0.905, 0.1, r'Frequency (cm$^{-1}$)'); 
fig.suptitle(dbname)

plt.show()