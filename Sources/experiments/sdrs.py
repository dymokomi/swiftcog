import random, textwrap

WIDTH = 64
ONES = 8  # active bits

MASK = (1 << WIDTH) - 1

random.seed(42)

def random_sdr():
    bits = random.sample(range(WIDTH), ONES)
    val = 0
    for b in bits:
        val |= 1 << b
    return val

def rotate_left(x, k):
    k %= WIDTH
    return ((x << k) | (x >> (WIDTH - k))) & MASK

def bitstring(x):
    return ''.join('#' if (x >> i) & 1 else '0' for i in reversed(range(WIDTH)))

def popcount_overlap(a, b):
    return bin(a & b).count('1')

# 1) create base vectors
C = random_sdr()          # Concept
M = random_sdr()          # Marker ("INSTANCE")
UID = random_sdr()        # Unique ID

# 2) role permutations
C_r  = rotate_left(C, 0)  # role 0
M_r  = rotate_left(M, 1)  # role 1
UID_r = rotate_left(UID, 2)  # role 2

# 3) bind into instance SDR
Instance = C_r ^ M_r ^ UID_r

# 4) unbind to recover concept
Recovered_C = rotate_left(Instance ^ M_r ^ UID_r, 0)

# 5) recover marker and unique ID
Recovered_M = rotate_left(Instance ^ C_r ^ UID_r, WIDTH - 1)  # rotate back by -1
Recovered_UID = rotate_left(Instance ^ C_r ^ M_r, WIDTH - 2)  # rotate back by -2

# 6) diagnostics
print("BIT LEGEND: # = 1, 0 = 0\n")
print("Concept  (C):       ", bitstring(C))
print("Marker   (M):       ", bitstring(M))
print("Unique ID(UID):     ", bitstring(UID))
print("- after role rotation -")
print("ρ^0(C):             ", bitstring(C_r))
print("ρ^1(M):             ", bitstring(M_r))
print("ρ^2(UID):           ", bitstring(UID_r))
print("\nXOR-bound Instance: ", bitstring(Instance))
print("\nRecovered Concept:  ", bitstring(Recovered_C))
print(f"\nOverlap between C and Recovered_C: {popcount_overlap(C, Recovered_C)} / {ONES} active bits")

print("\nRecovered Marker:   ", bitstring(Recovered_M))
print(f"Overlap between M and Recovered_M: {popcount_overlap(M, Recovered_M)} / {ONES} active bits")

print("\nRecovered UID:      ", bitstring(Recovered_UID))
print(f"Overlap between UID and Recovered_UID: {popcount_overlap(UID, Recovered_UID)} / {ONES} active bits")

