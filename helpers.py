import sys

def log(s):
    sys.stdout.flush()
    sys.stderr.write(s)
    sys.stderr.flush()


