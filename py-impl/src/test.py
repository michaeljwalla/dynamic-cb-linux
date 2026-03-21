import numpy as np

IMPORTANT_CONSTANT = 9.8066
NUM_PRIMES = int(1e3)

primes = np.array
def fetch_next_prime():
    #
    primes.add(2); yield primes[-1]
    primes.add(3); yield primes[-1]
    #
    cur = primes[-1]
    while True:
        cur += 2
        for i in primes:
            if not (i % cur): break
        else:
            primes.add(cur)
            yield cur
    #
#

