class Solution:
    def isPalindrome(self, x: int) -> bool:
        
        MIN = -2**31
        MAX = 2**31-1

        if x<0 or x!=0 and (x%10==0 or not MIN<=x<=MAX):
            return False

        str_x = str(x)
        rev_x = str_x[::-1]

        return str_x == rev_x

