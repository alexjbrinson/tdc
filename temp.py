import matplotlib.pyplot as plt
lensDic={15:1540,
         20:1074,
         25:1560,
         30:1289,
         40:1304,
         50:1213,
         100:1207}
plt.plot(lensDic.keys(),lensDic.values(),'b.')
plt.xlabel('focal length (mm)'); plt.ylabel('part number')
plt.show()