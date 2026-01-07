"""
String utilities with multiple quality issues and bugs.
"""

def reverse_string(s):
    # Missing docstring, no type hints
    reversed_str=""
    for i in range(len(s)-1,-1,-1):
        reversed_str+=s[i]
    return reversed_str

def count_vowels(text):
    # Missing docstring, hardcoded values, no case handling
    vowels=['a','e','i','o','u']
    count=0
    for char in text:
        if char in vowels:
            count+=1
    return count

def is_palindrome(word):
    # Missing docstring, inefficient implementation
    reversed_word=""
    for char in word:
        reversed_word=char+reversed_word
    return word==reversed_word

def capitalize_words(sentence):
    # Missing docstring, doesn't handle edge cases
    words=sentence.split(' ')
    capitalized=[]
    for word in words:
        capitalized.append(word[0].upper()+word[1:])
    return ' '.join(capitalized)

def remove_duplicates(text):
    # Missing docstring, inefficient algorithm
    result=""
    for char in text:
        if char not in result:
            result+=char
    return result

# Magic numbers everywhere
def truncate_string(s,length=10):
    # Missing docstring, magic number
    if len(s)>length:
        return s[:length]+"..."
    return s

class StringManipulator:
    # Missing docstring
    
    def __init__(self,text):
        self.text=text
    
    def to_upper(self):
        # Missing docstring
        return self.text.upper()
    
    def to_lower(self):
        # Missing docstring
        return self.text.lower()
    
    def word_count(self):
        # Bug: doesn't handle multiple spaces or punctuation
        return len(self.text.split(' '))
