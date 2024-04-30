DOCU = {
"print":"""
print arg1 arg2 ... argN;
    Prints the arguments of any type without a trailing new line.

Author of this: Darren Chase Papa
""",
"println":"""
println arg1 arg2 ... argN;
    Prints the arguments of any type with a trailing new line.

Author of this: Darren Chase Papa
""",
"input":"""
input variable-string prompt-string;
    Reads input from console.
    The prompt is printed without a trailing newline.

Author of this: Darren Chase Papa
""",
"set":"""
See: Variables, Objects
set name-string value-any;
    Sets a variable in the local scope.
    If the current scope is the global scope it will become a global variable.

Author of this: Darren Chase Papa
""",
"gset":"""
See: Variables, Objects
gset name-string value-any;
    Sets a global variable

Author of this: Darren Chase Papa
""",
"nset":"""
nset name-string value-any;
    
""",
"hello world":"""
println "Hello, world!"; # This is a comment :)), and yes the
other octothorpe is necessary #

Author of this: Darren Chase Papa
""",
}

doc = """
CSLang version 0.1:
    Cryptic Scripting Language is a programming langauge designed to have a simple
    interpreter and to have a simple syntax. Its interpreter was written on Python
    so dont complain about speed. CSLang has a long way to go, we are planning to
    make a Python API to interface with python classes. We are also planning to
    add asynchronous and concurrent tasks on CSLang. Oh and our lists indecies
    start at zero! Anyways do `docu_help "hello world"` to continue on your journey!
    Good luck!

CSLang Creator: Darren Chase Papa
CSLang team:
    [None :(]
Author of this: Darren Chase Papa
"""

def find_docu(text):
    if text == "":
        print("Enter a funcrion name or a string!")
        return
    print(DOCU.get(text,"{name}: Not Available").format(name=text))