from epics import caget, caput, cainfo
caput('XXX:m1.VAL', 1.90)
m1 = caget('XXX:m1.VAL')
print(m1)