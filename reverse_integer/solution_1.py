class Solution:
    def reverse(self, x: int) -> int: 
        num = math.fabs(x)
        rev = 0
        while num>0:
            rev = rev*10 + num%10
            num //= 10
        if not ((-2)**31) <= rev <= ((2**31)-1) :
            return 0
        return int(rev) if x>=0 else int(-rev)
