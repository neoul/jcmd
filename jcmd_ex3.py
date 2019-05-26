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
    cmds = {
        "argument": {
            "help": "method cmd example",
            "cmd": {
                "method": "my_method"
            },
            "args": {
                "madatory-data": {
                    "help": "mandatory data"
                },
                "optional-data": {
                    "help": "optional data",
                    "default": "no-option"
                },
                "range-data": {
                    "help": "range data",
                    "range": "<10-100>",
                    "default": 10
                },
                "enum-data": {
                    "help": "enum data",
                    "enum": [
                        "green",
                        "blue",
                        "red",
                        "yellow",
                        "bluesky"
                    ],
                    "default": "red"
                }
            }
        }
    }

    def my_method(self, **argument):
        print(argument)


if __name__ == "__main__":
    j = JcmdEx1()
    j.cmdloop()
