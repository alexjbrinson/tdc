import sqlite3 as sl
import sys, os
import time
import numpy as np
import pandas as pd
import math
from datetime import datetime
import pickle
import matplotlib.pyplot as plt

minToF=3500
maxToF=6500
channel=3
db_path="./data/scan17/scan17_allData.db"
sql_query="SELECT * from TDC WHERE channel == "+str(channel)+" AND tStamp >"+str(minToF)+" AND tStamp < "+str(maxToF)+" LIMIT 2000"
conn=sl.connect(db_path)

dframe= pd.read_sql_query(sql_query, conn)
conn.close()
print(dframe)