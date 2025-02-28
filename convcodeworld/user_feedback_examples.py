EXPERT_FEEDBACK_EXAMPLE = \
"""
Example Input:
Sort a list of integers in ascending order. The function should take a list of integers and return a sorted list. Ensure that the function handles negative numbers and zeros correctly. Check if the function's output is a sorted list.
```python
>>> sorted_list = sort_func([3, -1, 0, 5, -10, 2])
>>> sorted_list
[-10, -1, 0, 2, 3, 5]
```
You should write self-contained code starting with:
```python
def sort_func(int_list):
```

Ground Truth Code:
```python
def sort_func(int_list):
    return sorted(int_list)
```

Previous Code:
```python
def sort_func(int_list):
    for i in range(len(int_list)):
        for j in range(len(int_list) - 1):
            if int_list[j] < int_list[j + 1]:
                int_list[j], int_list[j + 1] = int_list[j + 1], int_list[j]
    return int_list

test_list = [3, -1, 0, 5, -10, 2]
print(sort_func(test_list))
```

Reasoning:
Let's think step by step in order to produce the user_feedback. We need to compare the `previous_code` with the `ground_truth_code` and identify specific areas where the `previous_code` deviates from the expected behavior. We should focus on the sorting algorithm, handling of edge cases like negative numbers and zeros, and the overall performance of the code.

User Feedback:
1. **Sorting Algorithm**: The `previous_code` implements a bubble sort algorithm, but it sorts the list in descending order due to the condition `if int_list[j] < int_list[j + 1]`. The correct approach should use `if int_list[j] > int_list[j + 1]` to sort in ascending order.

2. **Edge Case Handling**: While the `previous_code` attempts to handle all integers, it incorrectly sorts the list in the reverse order. Ensure that the sorting condition correctly compares elements to achieve ascending order.

3. **Code Simplicity and Readability**: The bubble sort implementation in the `previous_code` is more complex and less readable compared to using the built-in `sorted()` function. Simplifying the code to use `sorted()` will enhance readability and maintainability.

4. **Performance**: The bubble sort algorithm used in the `previous_code` has a time complexity of O(n^2), which can be inefficient for large lists. The `sorted()` function, on the other hand, uses Timsort, which has a time complexity of O(n log n) and is more suitable for sorting large datasets.

5. **Test Case Verification**: The `previous_code` includes a print statement to verify the function's output. While this is useful for debugging, consider using assertions or test functions to automate the verification process in a more scalable way.

Overall, the `previous_code` functions incorrectly by sorting the list in descending order. Using the correct comparison in the bubble sort condition or utilizing Python's built-in sorting capabilities would improve the function's correctness and performance.
"""



NOVICE_FEEDBACK_EXAMPLE = \
"""
Example Input:
Sort a list of integers in ascending order. The function should take a list of integers and return a sorted list. Ensure that the function handles negative numbers and zeros correctly. Check if the function's output is a sorted list.
```python
>>> sorted_list = sort_func([3, -1, 0, 5, -10, 2])
>>> sorted_list
[-10, -1, 0, 2, 3, 5]
```
You should write self-contained code starting with:
```python
def sort_func(int_list):
```

Ground Truth Code:
```python
def sort_func(int_list):
    return sorted(int_list)
```

Previous Code:
```python
def sort_func(int_list):
    for i in range(len(int_list)):
        for j in range(len(int_list) - 1):
            if int_list[j] < int_list[j + 1]:
                int_list[j], int_list[j + 1] = int_list[j + 1], int_list[j]
   return int_list

test_list = [3, -1, 0, 5, -10, 2]
print(sort_func(test_list))
```

Compilation Feedback:
Traceback (most recent call last):
  File "tmp.py", line 6
    return int_list
                   ^
IndentationError: unindent does not match any outer indentation level

Reasoning:
Let's think step by step in order to produce the novice-level `user_feedback`. 

User Feedback:
I got this error: 
```
Traceback (most recent call last):
  File "tmp.py", line 6
    return int_list
                   ^
IndentationError: unindent does not match any outer indentation level
```
I think there might be something wrong with the indentation of the `return int_list` line. Also, I think there exists a simpler way to sort a list in Python. 
"""



EXECUTION_EXPERT_FEEDBACK_EXAMPLE = \
"""
Example Input:
Sort a list of integers in ascending order. The function should take a list of integers and return a sorted list. Ensure that the function handles negative numbers and zeros correctly. Check if the function's output is a sorted list.
```python
>>> sorted_list = sort_func([3, -1, 0, 5, -10, 2])
>>> sorted_list
[-10, -1, 0, 2, 3, 5]
```
You should write self-contained code starting with:
```python
def sort_func(int_list):
```

Ground Truth Code:
```python
def sort_func(int_list):
    return sorted(int_list)
```

Previous Code:
```python
def sort_func(int_list):
    for i in range(len(int_list)):
        for j in range(len(int_list) - 1):
            if int_list[j] < int_list[j + 1]:
                int_list[j], int_list[j + 1] = int_list[j + 1], int_list[j]
    return int_list

test_list = [3, -1, 0, 5, -10, 2]
print(sort_func(test_list))
```

Execution Feedback:
TEST_CASE_1
Traceback (most recent call last):
  File "__test__.py", line 78, in test_case_1
AssertionError: sort_func([3, -1, 0, 5, -10, 2]) != [-10, -1, 0, 2, 3, 5]

Reasoning:
Let's think step by step in order to produce the user_feedback. We need to compare the `previous_code` with the `ground_truth_code` and identify specific areas where the `previous_code` deviates from the expected behavior. We should focus on the sorting algorithm, handling of edge cases like negative numbers and zeros, and the overall performance of the code.

User Feedback:
1. **Sorting Algorithm**: The `previous_code` implements a bubble sort algorithm, but it sorts the list in descending order due to the condition `if int_list[j] < int_list[j + 1]`. The correct approach should use `if int_list[j] > int_list[j + 1]` to sort in ascending order.

2. **Edge Case Handling**: While the `previous_code` attempts to handle all integers, it incorrectly sorts the list in the reverse order. Ensure that the sorting condition correctly compares elements to achieve ascending order.

3. **Code Simplicity and Readability**: The bubble sort implementation in the `previous_code` is more complex and less readable compared to using the built-in `sorted()` function. Simplifying the code to use `sorted()` will enhance readability and maintainability.

4. **Performance**: The bubble sort algorithm used in the `previous_code` has a time complexity of O(n^2), which can be inefficient for large lists. The `sorted()` function, on the other hand, uses Timsort, which has a time complexity of O(n log n) and is more suitable for sorting large datasets.

5. **Test Case Verification**: The `previous_code` includes a print statement to verify the function's output. While this is useful for debugging, consider using assertions or test functions to automate the verification process in a more scalable way.

Overall, the `previous_code` functions incorrectly by sorting the list in descending order. Using the correct comparison in the bubble sort condition or utilizing Python's built-in sorting capabilities would improve the function's correctness and performance.
"""


EXECUTION_NOVICE_FEEDBACK_EXAMPLE = \
"""
Example Input:
Sort a list of integers in ascending order. The function should take a list of integers and return a sorted list. Ensure that the function handles negative numbers and zeros correctly. Check if the function's output is a sorted list.
```python
>>> sorted_list = sort_func([3, -1, 0, 5, -10, 2])
>>> sorted_list
[-10, -1, 0, 2, 3, 5]
```
You should write self-contained code starting with:
```python
def sort_func(int_list):
```

Previous Code:
```python
def sort_func(int_list):
    for i in range(len(int_list)):
        for j in range(len(int_list) - 1):
            if int_list[j] < int_list[j + 1]:
                int_list[j], int_list[j + 1] = int_list[j + 1], int_list[j]
    return int_list

test_list = [3, -1, 0, 5, -10, 2]
print(sort_func(test_list))
```

Compilation Feedback:
No syntax errors

Execution Feedback:
TEST_CASE_1
Traceback (most recent call last):
  File "__test__.py", line 78, in test_case_1
AssertionError: sort_func([3, -1, 0, 5, -10, 2]) != [-10, -1, 0, 2, 3, 5]

Reasoning:
Let's think step by step in order to produce the novice-level `user_feedback`.

User Feedback:
I got this error: 
```
Traceback (most recent call last):
  File "__test__.py", line 78, in test_case_1
AssertionError: sort_func([3, -1, 0, 5, -10, 2]) != [-10, -1, 0, 2, 3, 5]
```
It seems like the function didn't sort the list correctly. The list is in descending order instead of ascending order. Also, I think there exists a simpler way to sort a list in Python. 
"""