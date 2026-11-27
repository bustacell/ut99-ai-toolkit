#!/usr/bin/env python3
import os, sys
d, want = sys.argv[1], int(sys.argv[2])
n = 0
if os.path.isdir(d):
    for i in range(1, want + 1):
        p = os.path.join(d, "%04d.png" % i)
        if os.path.exists(p) and os.path.getsize(p) > 2000:
            n += 1
print(n)
