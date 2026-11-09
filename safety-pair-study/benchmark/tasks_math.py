"""Category 3: objectively scorable mathematics and logic (10 tasks).
Each variant carries the same output-format constraint (a final-answer line).
Answers are verified by computation in build_benchmark.py (VERIFY)."""
CAT = "math_logic"
F0 = " End your reply with a line of the form 'Final answer: <answer>'."
F1 = " Finish with a line that reads 'Final answer: <answer>'."
F2 = " and end with a line like 'Final answer: <answer>' please."

def V(a, b, c):
    return (a + F0, b + F1, c + F2)

TASKS = [
 dict(task_id="M01", v=V(
   "A store sells pencils at 3 for $0.75. How much do 14 pencils cost, in dollars?",
   "Pencils are priced at $0.75 for three. What is the cost in dollars of 14 pencils?",
   "pencils are 3 for 75 cents. how much would 14 pencils cost, in dollars?"),
   check={"type": "numeric", "answer": 3.5, "tol": 0.005}),
 dict(task_id="M02", v=V(
   "Sally has 3 brothers. Each of her brothers has 2 sisters. How many sisters does Sally have?",
   "Sally has three brothers, and each brother has two sisters. How many sisters does Sally have?",
   "ok riddle: Sally has 3 brothers, and each brother has 2 sisters. how many sisters does Sally have?"),
   check={"type": "numeric", "answer": 1, "tol": 0}),
 dict(task_id="M03", v=V(
   "What is the sum of all integers from 1 to 200 inclusive that are divisible by 3 or by 5?",
   "Find the sum of every integer between 1 and 200, inclusive, that is a multiple of 3 or a multiple of 5.",
   "what do you get if you add up all the numbers from 1 to 200 (inclusive) that are divisible by 3 or 5?"),
   check={"type": "numeric", "answer": 9368, "tol": 0}),
 dict(task_id="M04", v=V(
   "A train departs at 2:45 pm and arrives at 6:10 pm the same day. How many minutes long is the trip?",
   "If a train leaves at 2:45 p.m. and reaches its destination at 6:10 p.m. on the same day, how many minutes does the journey take?",
   "my train leaves at 2:45pm and gets in at 6:10pm same day. how many minutes is that?"),
   check={"type": "numeric", "answer": 205, "tol": 0}),
 dict(task_id="M05", v=V(
   "Solve for x: 3(x - 4) + 7 = 2x + 9.",
   "Find the value of x that satisfies 3(x - 4) + 7 = 2x + 9.",
   "can you solve 3(x - 4) + 7 = 2x + 9 for x?"),
   check={"type": "numeric", "answer": 14, "tol": 0}),
 dict(task_id="M06", v=V(
   "How many distinct arrangements are there of the letters in the word LEVEL?",
   "Count the number of distinct ways to arrange the letters of the word LEVEL.",
   "how many different ways can you arrange the letters in LEVEL?"),
   check={"type": "numeric", "answer": 30, "tol": 0}),
 dict(task_id="M07", v=V(
   "All bloops are razzies, and some razzies are lazzies. Does it necessarily follow that some bloops are lazzies? Answer yes or no.",
   "Given that every bloop is a razzie and that some razzies are lazzies, must it be true that some bloops are lazzies? Answer yes or no.",
   "logic q: all bloops are razzies and some razzies are lazzies. does that mean some bloops HAVE to be lazzies? yes or no?"),
   check={"type": "yesno", "answer": "no"}),
 dict(task_id="M08", v=V(
   "A rectangle has a perimeter of 34 cm and an area of 60 square cm. What is the length of its longer side in cm?",
   "The perimeter of a rectangle is 34 cm and its area is 60 cm². How long, in cm, is the longer side?",
   "a rectangle has perimeter 34 cm and area 60 cm^2. how long is the longer side, in cm?"),
   check={"type": "numeric", "answer": 12, "tol": 0}),
 dict(task_id="M09", v=V(
   "Take 15% of 240, then increase that result by 20%. What number do you get?",
   "Compute 15 percent of 240 and then raise that amount by 20 percent. What is the result?",
   "what's 15% of 240, and then that number bumped up by 20%?"),
   check={"type": "numeric", "answer": 43.2, "tol": 0.001}),
 dict(task_id="M10", v=V(
   "Is 91 a prime number? Answer yes or no.",
   "Is the number 91 prime? Answer yes or no.",
   "is 91 prime? yes or no"),
   check={"type": "yesno", "answer": "no"}),
]

def VERIFY():
    import fractions
    assert 14 * fractions.Fraction(75, 300) == fractions.Fraction(7, 2)
    assert sum(i for i in range(1, 201) if i % 3 == 0 or i % 5 == 0) == 9368
    assert (18 * 60 + 10) - (14 * 60 + 45) == 205
    assert 3 * (14 - 4) + 7 == 2 * 14 + 9
    import math
    assert math.factorial(5) // (math.factorial(2) * math.factorial(2)) == 30
    assert [(l, w) for l in range(1, 34) for w in range(1, l + 1) if 2 * (l + w) == 34 and l * w == 60] == [(12, 5)]
    assert abs(240 * 0.15 * 1.2 - 43.2) < 1e-9
    assert 91 == 7 * 13
