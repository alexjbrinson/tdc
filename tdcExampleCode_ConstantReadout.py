import numpy as np 
from S15lib.instrumentsBrinson import TimeStampTDC1
import time
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import os
import multiprocessing
import threading
import serial

print('hi')

dev = TimeStampTDC1('COM3')
print('hey')
dev.level = dev.TTL_LEVELS #use ts.NIM_LEVELS for nim signals
#dev.int_time=.001
print(dev.int_time)
#dev.accumulated_timestamps_filename = 'timestamps.raw'

if os.path.exists(dev.accumulated_timestamps_filename):
      os.remove(
          dev.accumulated_timestamps_filename
      )  # remove previous accumulation file for a fresh start
else: pass


#dev.accumulate_timestamps = True
'''dev.proc = multiprocessing.Process(
    target=dev._continuous_stream_timestamps_to_file,
    args=(dev.accumulated_timestamps_filename,),
)
dev.proc.start()'''

# x = threading.Thread(
#     target=dev._continuous_stream_timestamps_to_file,
#     args=(dev.accumulated_timestamps_filename,),
# )
# #dev.proc.daemon = True  # Daemonize thread
# x.start()
dev.accumulated_timestamps_filename = 'timestamps2.raw'
dev.start_continuous_stream_timestamps_to_file()

for i in range(10):
  print('sleeping',i)
  time.sleep(0.1)

dev.stop_continuous_stream_timestamps_to_file()
#dev.continueStreaming=False
#dev._com.write(b"abort\r\n")
