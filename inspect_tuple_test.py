cat = "melee"
tup = ('thrown melee', 'melee mod')
s = f"{tup[0]} {tup[1]}"

print("cat in tup:", cat in tup) # False!
print("cat in s:", cat in s)     # True!
