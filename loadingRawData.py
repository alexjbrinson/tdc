import TDCutilities as tdcu
import numpy as np
import matplotlib.pyplot as plt

scan=121
file='../data/RFQ Tests/scan%d/scan%d_currentData.raw'%(scan,scan)
scanDict=tdcu.read_timestamps_from_file_as_dict(file)
triggers=scanDict['channel 1']
events  =scanDict['channel 3']

plt.plot(triggers, np.ones_like(triggers),'r.')
plt.plot(events  , np.ones_like(events),  'b.')
plt.show()