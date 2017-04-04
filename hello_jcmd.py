#!/usr/bin/env python3
# neoul@ymail.com
"""
Example for JSON Line-oriented Command class
"""
import jcmd

class MyCmd(jcmd.JCmd):
    prompt = "mycli> "

if __name__ == "__main__":
    j = MyCmd(history=True)
    hello = {
        "hello": {
            "help": "jcmd hello example",
            "cmd": {
                "shell": "echo HELLO {{name}}"
            },
            "args": {
                "name": "hello argument"
            }
        }
    }
    j.load(cmddict=hello)
    j.load(cmdfile="cmd.json")
    print(j.__class__)
    j.cmdloop()
