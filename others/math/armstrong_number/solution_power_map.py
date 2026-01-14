
class Solution:
    def isArmstrong(self, n: int) -> bool:
        """
        Armstrong number logic
        """
        if n<0:
            return False
        if n<10:
            return True
        
        power_map = {i: i**len(str(n)) for i in range(10)}

        sum, n1 = 0, n
        while n1>0:
            sum += power_map[n1%10]
            n1//=10

        return sum == n


# ------------------ Basic Tests ------------------

def run_tests():
    sol = Solution()

    test_cases = [
        (0, True),
        (1, True),
        (9, True),
        (10, False),
        (153, True),
        (370, True),
        (371, True),
        (407, True),
        (9474, True),
        (9475, False),
    ]

    for n, expected in test_cases:
        result = sol.isArmstrong(n)
        assert result == expected, (
            f"FAILED: isArmstrong({n})\n"
            f"Expected: {expected}\n"
            f"Got: {result}"
        )

    print("✅ All tests passed")


if __name__ == "__main__":
    run_tests()