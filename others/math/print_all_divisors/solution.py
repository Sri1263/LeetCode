import math

class Solution:
    def print_divisors(self, n: int) -> list[int]:
        """
        Write your divisor-finding logic here
        Return all divisors of n (order doesn't matter unless you sort)
        """
        
        divisors = [1]

        if n == 1:
            return divisors

        for i in range(2, int(math.sqrt(n))+1):
            if n%i==0:
                divisors.append(i)
                if i!=n//i:
                    divisors.append(n//i)

        divisors += [n]

        return divisors



# ------------------ Tests (fail fast) ------------------
def run_tests():
    sol = Solution()

    test_cases = [
        (1, [1]),
        (2, [1, 2]),
        (3, [1, 3]),
        (4, [1, 2, 4]),
        (6, [1, 2, 3, 6]),
        (12, [1, 2, 3, 4, 6, 12]),
        (25, [1, 5, 25]),
        (36, [1, 2, 3, 4, 6, 9, 12, 18, 36]),
    ]

    for n, expected in test_cases:
        result = sol.print_divisors(n)
        assert sorted(result) == expected, (
            f"FAILED TEST CASE\n"
            f"print_divisors({n})\n"
            f"Expected: {expected}\n"
            f"Got: {sorted(result)}"
        )

    print("✅ All tests passed")


if __name__ == "__main__":
    run_tests()