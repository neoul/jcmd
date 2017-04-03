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


## Further study

- Scripting
- Enumeration, range and pattern for argument

