# JCmd
The class to build line-oriented command interpreters using JSON and dictionary

This class is used to provide a simple framework for writing line-oriented
command interpreters. The user-defined commands written in Python dictionary 
or JSON format are loaded and executed by this class.

This class is based on Python cmd library that is a motivation to make it.
It would be more useful due to the following conveniences.

- It supports hierarchical command tree as communication equipment's CLI.
- It supports to load and execute commands from JSON or Python dictionary.
- It supports built-in tab-completion.
    - less considerable tab-completion
- It supports arguments separated from The commands.
- It supports shell command execution and Python function call.
- It supports to show the help of the command in detail.
- It supports the brief command list (The key is mapping to '?' or 'list')
- It supports the sub mode.
  - It loads a different command tree at runtime.
- It supports the default value for the argument.

## Usage

### Using JSON command file

cmd.json

``` json
{
    "network": {
        "help": "network tools for diagnostics",
        "ping": {
            "help": "network reachability test of a host with transmission count",
            "cmd": {
                "shell": [
                    "ping {{ip}} -c {{count}}"
                ]
            },
            "args": {
                "ip": "IP address",
                "count": {
                    "help": "The number of transmit",
                    "default": 5
                }
            }
        }
    }
}
```

``` shell
python3 jcmd.py cmd.json
jcmd> network ping ip=192.168.0.100
```

### Inherited Class

```python
class JcmdEx1(jcmd.JCmd):
    prompt = "mycli> "
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

    def my_method(self, argument):
        print("my-method", argument)

if __name__ == "__main__":
    j = JcmdEx1()
    j.cmdloop()

```

## Further study

- Scripting
- Enumeration, range and pattern for argument

## argument options

- type: path
- default: ANYVALUE
- range: <1-24>
- pattern: PATTERN
- enum: [A,B,C,D]