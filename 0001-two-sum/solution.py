class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        if not (2 <= len(nums) <= 10**4) or not (-10**9 <= target <= 10**9):
            return 0

        nums_map = {}

        for i in range(len(nums)):
            complement = target - nums[i]
            if complement in nums_map:
                return [i, nums_map[complement]]
            nums_map[nums[i]] = i

