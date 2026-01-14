
class Solution:
    def gcd(self, a: int, b: int) -> int:
        """
        GCD logic
        """

        if a == 0 or b == 0:
            return max(a,b)

        for i in range(min(a,b)+1, 1, -1):
            if a%i == 0 == b%i:
                return i

        return 1


# ------------------ Basic Tests ------------------
def run_tests():
    sol = Solution()

    test_cases = [
        (0, 0, 0),
        (0, 5, 5),
        (5, 0, 5),
        (1, 1, 1),
        (12, 18, 6),
        (18, 12, 6),
        (17, 13, 1),
        (100, 10, 10),
        (270, 192, 6),
    ]

    for a, b, expected in test_cases:
        result = sol.gcd(a, b)
        assert result == expected, (
            f"FAILED: gcd({a}, {b})\n"
            f"Expected: {expected}\n"
            f"Got: {result}"
        )

    print("✅ All tests passed")


if __name__ == "__main__":
    run_tests()