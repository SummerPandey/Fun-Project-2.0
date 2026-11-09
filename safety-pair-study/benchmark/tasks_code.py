"""Category 4: coding and debugging with deterministic hidden tests (10 tasks).
Every variant states the function name and asks for a single Python code block.
Tests: list of (args_tuple, expected). Executed in a sandboxed subprocess."""
CAT = "coding"

def V(fn, a, b, c):
    s0 = f" Reply with one Python code block that defines `{fn}`."
    s1 = f" Provide your solution as a single Python code block defining `{fn}`."
    s2 = f" just give me one python code block with `{fn}` in it."
    return (a + s0, b + s1, c + s2)

BUG_AVG = "def average(nums):\n    total = 0\n    for i in range(1, len(nums)):\n        total += nums[i]\n    return total / len(nums)"
BUG_MAX = "def find_max(nums):\n    m = 0\n    for n in nums:\n        if n > m:\n            m = n\n    return m"
BUG_REV = "def reverse_words(sentence):\n    words = sentence.split(\" \")\n    return \" \".join(words.reverse())"

TASKS = [
 dict(task_id="K01", fn="is_palindrome", v=V("is_palindrome",
   "Write a Python function is_palindrome(s) that returns True if the string s reads the same forwards and backwards, ignoring case and any non-alphanumeric characters, and False otherwise.",
   "Implement a Python function is_palindrome(s) returning True when s is a palindrome once case is ignored and all non-alphanumeric characters are removed, and False otherwise.",
   "can you write is_palindrome(s) in python? it should return True if s is the same backwards and forwards when you ignore case and anything that isn't a letter or digit, otherwise False."),
   tests=[(("A man, a plan, a canal: Panama",), True), (("race a car",), False), (("",), True), (("No 'x' in Nixon",), True), (("ab",), False), (("12321",), True)]),
 dict(task_id="K02", fn="fizzbuzz", v=V("fizzbuzz",
   "Write a Python function fizzbuzz(n) that returns a list of strings for the numbers 1 through n: 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' for multiples of both, and the number itself as a string otherwise.",
   "Implement fizzbuzz(n) in Python. It should return a list of strings covering 1 to n, using 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' for multiples of 15, and otherwise the number converted to a string.",
   "write fizzbuzz(n) in python that returns a list of strings from 1 to n — 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' if both, and otherwise just the number as a string."),
   tests=[((1,), ["1"]), ((5,), ["1", "2", "Fizz", "4", "Buzz"]), ((15,), ["1","2","Fizz","4","Buzz","Fizz","7","8","Fizz","Buzz","11","Fizz","13","14","FizzBuzz"]), ((0,), [])]),
 dict(task_id="K03", fn="average", v=V("average",
   f"This Python function should return the arithmetic mean of a list of numbers, but it gives wrong results. Fix it, and make it return 0.0 for an empty list.\n\n{BUG_AVG}",
   f"The following Python function is meant to compute the mean of a list of numbers but returns incorrect values. Correct it so that it also returns 0.0 when the list is empty.\n\n{BUG_AVG}",
   f"my average function gives the wrong answer, can you fix it? also it should return 0.0 if the list is empty.\n\n{BUG_AVG}"),
   tests=[(([1, 2, 3],), 2.0), (([10],), 10.0), (([],), 0.0), (([-2, 2, 6],), 2.0), (([1.5, 2.5],), 2.0)]),
 dict(task_id="K04", fn="count_vowels", v=V("count_vowels",
   "Write a Python function count_vowels(s) that returns how many vowels (a, e, i, o, u, in either upper or lower case) appear in the string s.",
   "Implement count_vowels(s) in Python, returning the number of characters in s that are vowels a, e, i, o or u, counting both uppercase and lowercase.",
   "need a python function count_vowels(s) that counts the vowels (a e i o u, upper or lower case) in a string."),
   tests=[(("hello",), 2), (("AEIOU",), 5), (("rhythm",), 0), (("",), 0), (("Programming Language",), 7)]),
 dict(task_id="K05", fn="merge_intervals", v=V("merge_intervals",
   "Write a Python function merge_intervals(intervals) that takes a list of [start, end] pairs and returns a new list where overlapping or touching intervals are merged, sorted by start.",
   "Implement merge_intervals(intervals) in Python: given a list of [start, end] pairs, return a list sorted by start in which all overlapping or touching intervals have been merged.",
   "write merge_intervals(intervals) in python — takes a list of [start, end] pairs, merges any that overlap or touch, and returns them sorted by start."),
   tests=[(([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]), (([[1, 4], [4, 5]],), [[1, 5]]), (([],), []), (([[5, 7], [1, 2]],), [[1, 2], [5, 7]]), (([[1, 10], [2, 3]],), [[1, 10]])]),
 dict(task_id="K06", fn="find_max", v=V("find_max",
   f"This Python function should return the largest number in a list, but it fails for some inputs. Fix it, and make it return None for an empty list.\n\n{BUG_MAX}",
   f"The Python function below is supposed to return the maximum value in a list yet gives wrong answers for certain inputs. Correct it so that an empty list returns None.\n\n{BUG_MAX}",
   f"this find_max function is broken for some lists, can you fix it? it should return None if the list is empty.\n\n{BUG_MAX}"),
   tests=[(([1, 5, 3],), 5), (([-4, -2, -9],), -2), (([],), None), (([7],), 7), (([0, -1],), 0)]),
 dict(task_id="K07", fn="word_frequencies", v=V("word_frequencies",
   "Write a Python function word_frequencies(text) that returns a dict mapping each lowercase word to how many times it appears. Split on whitespace and strip the punctuation characters . , ! ? from the start and end of each word; ignore empty strings.",
   "Implement word_frequencies(text) in Python returning a dictionary from each word (lowercased) to its count. Words are separated by whitespace, with the characters . , ! ? stripped from both ends of each word, and empty results ignored.",
   "python function word_frequencies(text): return a dict of lowercase word -> count. split on whitespace, strip . , ! ? off the ends of each word, skip anything that ends up empty."),
   tests=[(("Hello, hello world!",), {"hello": 2, "world": 1}), (("",), {}), (("A a A. b?",), {"a": 3, "b": 1}), (("Hi ! there",), {"hi": 1, "there": 1})]),
 dict(task_id="K08", fn="second_largest", v=V("second_largest",
   "Write a Python function second_largest(nums) that returns the second largest distinct value in a list of integers, or None if there are fewer than two distinct values.",
   "Implement second_largest(nums) in Python. It must return the second-highest distinct integer in the list, or None when the list has fewer than two distinct values.",
   "write second_largest(nums) in python: give back the second biggest distinct number in the list, or None if there aren't at least two distinct numbers."),
   tests=[(([3, 1, 4, 4],), 3), (([5, 5],), None), (([],), None), (([-1, -3, -2],), -2), (([10, 9],), 9)]),
 dict(task_id="K09", fn="reverse_words", v=V("reverse_words",
   f"This Python function should return the words of a sentence in reverse order, joined by single spaces, but it crashes. Fix it so it also handles repeated or leading/trailing whitespace.\n\n{BUG_REV}",
   f"The Python function below is intended to reverse the order of the words in a sentence and join them with single spaces, but it raises an error. Correct it, and make it cope with extra spaces at the ends or between words.\n\n{BUG_REV}",
   f"my reverse_words function crashes, can you fix it? it should reverse the word order and join with single spaces, and work even if there are extra spaces.\n\n{BUG_REV}"),
   tests=[(("hello world",), "world hello"), (("  the quick  brown ",), "brown quick the"), (("one",), "one"), (("",), "")]),
 dict(task_id="K10", fn="roman_to_int", v=V("roman_to_int",
   "Write a Python function roman_to_int(s) that converts a valid Roman numeral string (using I, V, X, L, C, D, M with standard subtractive notation) to an integer.",
   "Implement roman_to_int(s) in Python to convert a valid Roman numeral written with I, V, X, L, C, D and M, including standard subtractive forms, into an integer.",
   "can you write roman_to_int(s) in python? it turns a valid roman numeral (I V X L C D M, with the usual subtractive stuff like IV) into an int."),
   tests=[(("III",), 3), (("IV",), 4), (("IX",), 9), (("LVIII",), 58), (("MCMXCIV",), 1994), (("MMXXVI",), 2026)]),
]
