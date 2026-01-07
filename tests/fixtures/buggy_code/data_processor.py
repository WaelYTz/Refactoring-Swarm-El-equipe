"""
Data Processor with bugs, missing error handling, and poor practices.
"""

def process_data(data):
    # Missing docstring, no type hints, no error handling
    result=[]
    for item in data:
        if item>0:
            result.append(item*2)
    return result

def filter_even_numbers(numbers):
    # Missing docstring, inefficient implementation
    even_nums=[]
    for n in numbers:
        if n%2==0:
            even_nums.append(n)
    return even_nums

def get_max_value(values):
    # Bug: doesn't handle empty list
    max_val=values[0]
    for v in values:
        if v>max_val:
            max_val=v
    return max_val

def parse_csv_line(line):
    # Missing docstring, no error handling, assumes format
    parts=line.split(',')
    return {'name':parts[0],'age':int(parts[1]),'city':parts[2]}

class DataAnalyzer:
    def __init__(self,data):
        # Missing docstring
        self.data=data
        self.results=None
    
    def analyze(self):
        # Missing docstring, vague implementation
        total=0
        for item in self.data:
            total+=item
        self.results=total/len(self.data)
        return self.results
    
    def get_summary(self):
        # Bug: doesn't check if analyze() was called first
        return f"Average: {self.results}"

# Global variable (bad practice)
GLOBAL_COUNTER=0

def increment_counter():
    global GLOBAL_COUNTER
    GLOBAL_COUNTER+=1
    return GLOBAL_COUNTER
