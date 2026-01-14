
"""

Euclidean Algorithm:

The Euclidean Algorithm is a method for finding the greatest common divisor (GCD)
of two numbers. It operates on the principle that the GCD of two numbers remains
the same even if the smaller number is subtracted from the larger number.

"""

class Solution:
    def gcd(self, a: int, b: int) -> int:
        """
        GCD logic
        """

        if a == 0 or b == 0:
            return max(a,b)

        while a>0 and b>0:
            if a>b:
                a%=b # same as subtracting a from b, n times until b becomes smaller
            else:
                b%=a
            
        return a if b==0 else b


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