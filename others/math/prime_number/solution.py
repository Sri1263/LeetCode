import math

class Solution:
    def is_prime(self, n: int) -> bool:
        """
        prime-check logic
        """

        if n in [0,1]:
            return False
        

        for i in range (2, int(math.sqrt(n))+1):
            if n%i == 0:
                return False

        return True



# ------------------ Tests (fail fast, clean log) ------------------
def run_tests():
    sol = Solution()

    test_cases = [
        (0, False),
        (1, False),
        (2, True),
        (3, True),
        (4, False),
        (5, True),
        (9, False),
        (11, True),
        (25, False),
        (29, True),
        (49, False),
        (97, True),
        (100, False),
    ]

    for n, expected in test_cases:
        result = sol.is_prime(n)

        assert result == expected, (
            "FAILED TEST CASE\n"
            f"is_prime({n})\n"
            f"Expected: {expected}\n"
            f"Got: {result}"
        )

    print("✅ All tests passed")


if __name__ == "__main__":
    run_tests()