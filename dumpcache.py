import sys
import pickle
from pprint import pprint

with open(sys.argv[1], "rb") as f:
    x = pickle.load(f)
    pprint(x)
