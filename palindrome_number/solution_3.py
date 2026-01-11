class Solution:
    def isPalindrome(self, x: int) -> bool:
        
        MIN = -2**31
        MAX = 2**31-1

        if not MIN <= x <= MAX or x<0:
            return False

        rev, num = 0, x

        while num>0:
            rev = rev*10 + num%10
            num//=10

        return x == rev