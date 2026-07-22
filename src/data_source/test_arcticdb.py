import time
from datetime import datetime

import arcticdb as adb
import numpy as np
import pandas as pd

NUM_COLUMNS=10
NUM_ROWS=525600*3

df = pd.DataFrame(np.random.randint(0,100,size=(NUM_ROWS, NUM_COLUMNS)), 
                  columns=[f"COL_{i}" for i in range(NUM_COLUMNS)], 
                  index=pd.date_range('2000', periods=NUM_ROWS, freq='min'))

df2 = pd.DataFrame(np.random.randint(0,100,size=(NUM_ROWS, NUM_COLUMNS)), 
                  columns=[f"COL_{i}" for i in range(NUM_COLUMNS)], 
                  index=pd.date_range('2001', periods=NUM_ROWS, freq='min'))

ac = adb.Arctic("lmdb:///Leon/SideProject/quant")
# ac.create_library('travel_data')
print(ac.list_libraries())

lib = ac['travel_data']
lib.write("my_data", df)

st = time.time()
data = lib.read("my_data", date_range=(datetime(2000, 1, 3, 0, 0), datetime(2000, 1, 4, 15, 0)))
print(data.data, data.data.shape, data.data.shape[0]/1440)
print(time.time()-st)

st = time.time()
data = lib.read("my_data", date_range=(datetime(2002, 12, 30, 0, 0), datetime(2003, 1, 4, 15, 0)))
print(data.data, data.data.shape, data.data.shape[0]/1440)
print(time.time()-st)

lib.update('my_data', df2)

st = time.time()
data = lib.read("my_data", date_range=(datetime(2000, 1, 3, 0, 0), datetime(2000, 1, 4, 15, 0)))
print(data.data, data.data.shape, data.data.shape[0]/1440)
print(time.time()-st)

st = time.time()
data = lib.read("my_data", date_range=(datetime(2002, 12, 30, 0, 0), datetime(2003, 1, 4, 15, 0)))
print(data.data, data.data.shape, data.data.shape[0]/1440)
print(time.time()-st)


st = time.time()
data = lib.read("my_data", date_range=(datetime(2000, 4, 3, 0, 0), datetime(2000, 1, 9, 15, 0)))
print(data.data, data.data.shape, data.data.shape[0]/1440)
print(time.time()-st)

st = time.time()
data = lib.read("my_data", date_range=(datetime(2000, 4, 3, 0, 0), datetime(2000, 12, 29, 15, 0)))
print(data.data, data.data.shape, data.data.shape[0]/1440)
print(time.time()-st)

st = time.time()
data = lib.read("my_data", date_range=(datetime(2000, 4, 3, 0, 0), datetime(2008, 12, 29, 15, 0)))
print(data.data, data.data.shape, data.data.shape[0]/1440)
print(time.time()-st)

pass