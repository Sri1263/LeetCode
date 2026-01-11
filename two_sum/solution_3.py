class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        if not (2 <= len(nums) <= 10**4) or not (-10**9 <= target <= 10**9):
            return 0
        for i in range(len(nums)):
            for j in range (i+1,(len(nums))):
                if nums[i]+nums[j] == target:
                    return [i, j]
