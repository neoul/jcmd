#!/usr/bin/env python3
# neoul@ymail.com
"""
Example for Json Command Interface library
"""
import jcmd

class mycmd(jcmd.JCmd):
    #prompt = "mycli> "
    pass

if __name__ == "__main__":
    j = jcmd.JCmd()
    hello = {
        "hello": {
            "help": "jcmd hello example",
            "cmd": {
                "shell": "echo HELLO {name}"
            },
            "args": {
                "name": "hello argument"
            }
        }
    }
    j.load(cmddict=hello)
    j.load(cmdfile="cmd.json")
    j.prompt = "hello> "
    j.cmdloop()
