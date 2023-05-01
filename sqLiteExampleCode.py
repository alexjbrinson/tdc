import sqlite3 as sl
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

dev = TimeStampTDC1('COM3')
print('successful connection to TDC device')
dev.level = dev.TTL_LEVELS #use ts.NIM_LEVELS for nim signals
dev.accumulated_timestamps_filename = 'timestamps.raw'
(times,channels) = dev.read_timestamps_from_file()
times=[int(t) for t in times]
channels = [int(ch, 2) for ch in channels]
data = list(zip(times,channels))
print(type(times[0]))
#print(data)

con= sl.connect('newdb.db')
# with con:
#         con.execute("""
#         CREATE TABLE IF NOT EXISTS TDC (
#             tStamp INTEGER NOT NULL PRIMARY KEY,
#             channel INTEGER
#         );
#         """)

# sql = 'INSERT OR IGNORE INTO TDC (tStamp, channel) values(?, ?)'
# with con: con.executemany(sql, data)

with con:
    data = con.execute("SELECT * FROM TDC WHERE channel == 2")
    for row in data:
        print(row)