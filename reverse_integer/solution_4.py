class Solution:
    def reverse(self, x: int) -> int: 
        MIN = -2**31
        MAX = 2**31-1
        negative = x<0

        num = str(abs(x))
        reverse = int(num[::-1]) * (-1 if negative else 1)

        return reverse if MIN <= reverse <= MAX else 0
