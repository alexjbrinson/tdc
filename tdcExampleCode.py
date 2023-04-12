import numpy as np 
from S15lib.instruments import TimeStampTDC1
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt

ch1 = 1 
ch2 = 2 
ch3 = 4 
ch4 = 8

'''def func(i):
  return(int(i,2))
vfunc=np.vectorize(func)'''

dev = TimeStampTDC1('COM3')
dev.level = dev.TTL_LEVELS #use ts.NIM_LEVELS for nim signals 
'''t,p = dev.get_timestamps(t_acq=1)
t0=time.time()
p_int = np.array([ int(I,2) for I in p])

t1 = t[p_int==ch1] 
t2 = t[p_int==ch2] 
t3 = t[p_int==ch3] 
t4 = t[p_int==ch4]'''

def TDC1_trig_time(TDC1_get_timestamps, save_to_folder=''):
  '''
  Converts trigger (ch1) and measurement (ch2) channel
  inputs of the S-fifteen TDC1 card into relative time
  stamps in ns with respect to each trigger pulse.
  
  :param TDC1_get_timestamps: output of TimeStampTDC1(
                'dev/...').get_timestamps(t_acq=...)
  '''
  t_all, ch_base2 = TDC1_get_timestamps
  ch_no = np.array([ int(i,2) for i in ch_base2])
  df = pd.DataFrame({'t_all': t_all, 'ch_no': ch_no})
  ch_np = df[df.ch_no == 1].t_all.to_numpy() #trigger times

  time_now = datetime.datetime.utcnow().isoformat() #huh?
  dict_t = {}
  for t_trig_idx in range(len(ch_np)-1):
    t0=ch_np[t_trig_idx]; t1=ch_np[t_trig_idx+1]; print('Δt=',t1-t0)
    if t1-t0<1000:pass #temporary fix to avoid accidental triggers
    else:
      df_tmp = df[(df.ch_no == 2) &
            (df.t_all > ch_np[t_trig_idx]) &
            (df.t_all < ch_np[t_trig_idx+1])].copy(deep=True) #timestamps for events occuring between 2 trigger times
      df_tmp.t_all -= int(ch_np[t_trig_idx]) #subtracting off absolute trigger time
      dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)] = df_tmp.t_all.to_numpy()
      print(time_now+'UTC-trig{}: {} counts'.format(t_trig_idx, len(dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)])))
  t2=ch_np[-1]
  if t2-t1<1000: pass
  else:
    df_tmp = df[(df.ch_no == 2) &
          (df.t_all > ch_np[-1])].copy(deep=True)
    df_tmp.t_all -= int(ch_np[-1])
    dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)] = df_tmp.t_all.to_numpy()
  print(time_now+'UTC-trig{}: {} counts'.format(t_trig_idx, len(dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)])))
  if save_to_folder != '':
    print(dict_t.keys())
    for i in dict_t.keys():
      dict_t[i].tofile(save_to_folder+i+'-{}counts-ToF[ns].csv'.format(len(dict_t[i])), sep=',', format='%s')
  return dict_t

#dfx = pd.DataFrame.from_dict(TDC1_trig_time(dev.get_timestamps(t_acq=10)), orient='index').T
#dfx
dt=[]
t_acq=0.5
t_all, ch_base2 = dev.get_timestamps(t_acq=t_acq)
ch_no = np.array([ int(i,2) for i in ch_base2])
df = pd.DataFrame({'t_all': t_all, 'ch_no': ch_no})
ch_np = df[df.ch_no == 1].t_all.to_numpy()
print(np.array(t_all)[ch_no==1])
print(np.array(t_all)[ch_no==2])
time_now = datetime.datetime.utcnow().isoformat() #huh?
dict_t = {}
for t_trig_idx in range(len(ch_np)-1):
  print(ch_np[t_trig_idx])
  t0=ch_np[t_trig_idx]; t1=ch_np[t_trig_idx+1]; print('Δt=',t1-t0)
  if t1-t0<100:pass #temporary fix to avoid accidental triggers
  else:
    df_tmp = df[(df.ch_no == 2) &
          (df.t_all > ch_np[t_trig_idx]) &
          (df.t_all < ch_np[t_trig_idx+1])].copy(deep=True) #timestamps for events occuring between 2 trigger times
    df_tmp.t_all -= int(ch_np[t_trig_idx]) #subtracting off absolute trigger time
    dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)] = df_tmp.t_all.to_numpy()
    print(time_now+'UTC-trig{}: {} counts'.format(t_trig_idx, len(dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)])))

t_trig_idx=len(ch_np)-1

df_tmp = df[(df.ch_no == 2) &
      (df.t_all > ch_np[-1])].copy(deep=True)
df_tmp.t_all -= int(ch_np[-1])
dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)] = df_tmp.t_all.to_numpy()
print(time_now+'UTC-trig{}: {} counts'.format(t_trig_idx, len(dict_t[time_now+'UTC-trig{}'.format(t_trig_idx)])))

allRelativeTimes=np.array([])
for key in dict_t.keys():
  print(key)
  allRelativeTimes=np.append(allRelativeTimes,dict_t[key])
print(len(allRelativeTimes))

counts, bins = np.histogram(allRelativeTimes,bins=10000)
plt.stairs(counts, bins)
plt.show()