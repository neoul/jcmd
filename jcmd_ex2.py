#!/usr/bin/env python3
# neoul@ymail.com
"""
Example 1 for JSON Line-oriented Command class
"""
import jcmd


def my_func(first, second):
    print("my_func", first, second)


class JcmdEx1(jcmd.JCmd):
    prompt = "mycli> "
    

    def my_method(self, argument):
        print("my-method", argument)


if __name__ == "__main__":
    j = JcmdEx1()
    cmds = {
        "hello": {
            "help": "shell cmd exammeple",
            "cmd": {
                "shell": "echo HELLO {{name}}"
            },
            "args": {
                "name": "hello argument"
            }
        },
        "my-func": {
            "help": "func cmd exammeple",
            "cmd": {
                "func": [
                    'import jcmd_ex1',
                    'jcmd_ex1.my_func(first, second)'
                ]
            },
            "args": {
                "first": "first argument",
                "second": "second argument"
            }
        },
        "my-method": {
            "help": "method cmd example",
            "cmd": {
                "method": "my_method"
            },
            "args": {"argument": "my-method argument"}
        }
    }
    j.load(cmddict=cmds)
    j.cmdloop()