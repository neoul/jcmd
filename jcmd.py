#!/usr/bin/env python3
"""
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
- It supports the brief command list (The key is mapping to '?')
- It supports the sub mode.
  - It loads a different command tree at runtime.
- It supports the default value for the argument.


Further study

- Scripting
- Enumeration, range and pattern for argument
- Command tree setup using YAML

neoul@ymail.com
"""
import sys
import string
import json
import glob
import shlex
import subprocess
import shutil
import textwrap
try:
    import readline
except ImportError:
    import pyreadline


def is_windows():
    """Check if the host is windows."""
    try:
        import platform
        if platform.system() == 'Windows':
            return True
    except ImportError:
        return False
    return False


IS_WINDOWS = is_windows()

__all__ = ["JCmd"]

PROMPT = 'jcmd> '
IDENTCHARS = string.ascii_letters + string.digits + '_'

CMD = "cmd"
ARGS = "args"
HELP = "help"
NO_HELP = "no help"
LIST = "list"
FUNC = "func"
METHOD = "method"
SHELL = "shell"
SUBTREE = "subtree"
EXEC_SHELL = "!"
BRIEF_HELP = "?"
EOF = "EOF"
COMPLETE = "complete"
COMPLETE_IGNORES = set([EXEC_SHELL, BRIEF_HELP, EOF])

class JNode(dict):
    """JSON Command Tree Node"""

    def __init__(self, *args, **kargs):
        self.func = None
        self.shell = None
        self.method = None
        self.subtree = None
        super().__init__(*args)
        try:
            self.__doc__ = self[HELP]
            del self[HELP]
        except KeyError:
            self.__doc__ = NO_HELP
        try:
            for key, value in self[CMD].items():
                setattr(self, key, value)
            del self[CMD]
            self.eoc = True  # End of cmd
        except KeyError:
            self.eoc = False
        if self.eoc:
            try:
                self.args = self[ARGS]
                del self[ARGS]
            except KeyError:
                self.args = JNode()
            finally:
                self.update_args()

        if "cmddict" in kargs:
            self.load_from_dict(kargs["cmddict"])
        if "cmdjson" in kargs:
            self.load_from_json(kargs["cmdjson"])
        if "cmdfile" in kargs:
            self.load_from_file(kargs["cmdfile"])

    # def __missing__(self, key):
    #     return JNode()

    def update_args(self):
        """Update the arguments of the JSON Command Tree Node"""
        for key, value in self.args.items():
            if not isinstance(value, dict):
                self.args[key] = JNode({"help": value})

    def load_from_dict(self, dic):
        """Load JSON Command Tree Node from a dictionary"""
        jdata = json.dumps(dic)
        self.load_from_json(jdata)

    def load_from_json(self, jdata):
        """Load JSON Command Tree Node from json string"""
        def hooker(dic):
            """hooker for loading JSON Command Tree."""
            return JNode(dic)
        self.update(json.loads(jdata, object_hook=hooker))

    def load_from_file(self, cmdfile=None):
        """Load JSON Command Tree Node from json file"""
        with open(cmdfile, "r") as cfile:
            self.load_from_json(cfile.read())

    def find(self, jnodes=(), bestmatch=False):
        """Find a JSON Command Tree Node in command tree"""
        index = 0
        cnode = self
        for i, jnode in enumerate(jnodes):
            try:
                cnode = cnode[jnode]
                index = i + 1
            except KeyError:
                if bestmatch:
                    return index, cnode
                return index, JNode()
        return index, cnode


class JCmd:
    """Line-oriented Command class using JSON and dictionary"""
    prompt = PROMPT
    identchars = IDENTCHARS
    intro = "\n[Line-oriented Command Interface using JSON]\n"
    completion_matches = list()
    end = False
    line = ''
    cmds = None

    def __init__(
            self, stdin=None, stdout=None, history=None, **kargs):
        """Instantiate a JSON Line-oriented Command class"""
        self.cmdtree = JNode()  # JCmd command tree
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.old_completer = None

        if history:
            if not isinstance(history, bool):
                self.history_file = history
            else:
                self.history_file = '.' + self.__class__.__name__
            try:
                readline.read_history_file(self.history_file)
            except FileNotFoundError as ex:
                pass
        try:
            self.load(**kargs)
        except (FileNotFoundError, json.decoder.JSONDecodeError) as ex:
            self.stdout.write("%s\n" % ex)
        except KeyError as ex:
            pass

        # Built-in commands
        self.cmdtree[EOF] = JNode({
            HELP: "quit (ctrl+d)",
            CMD: {METHOD: "do_eof"}})
        self.cmdtree['quit'] = self.cmdtree[EOF]
        self.cmdtree['exit'] = self.cmdtree[EOF]
        self.cmdtree[EXEC_SHELL] = JNode({
            HELP: "execute a shell command",
            CMD: {SHELL: "{{shell-cmd}}"},
            ARGS: {"shell-cmd": "executable shell command"}})
        self.cmdtree[HELP] = JNode({
            HELP: "show a command help",
            CMD: {
                METHOD: "do_help",
                COMPLETE: "complete_help"
            }
        })
        self.cmdtree[BRIEF_HELP] = JNode({
            HELP: "show all the commands' help briefly",
            CMD: {
                METHOD: "do_help_briefly",
                COMPLETE: "complete_help"
            }
        })
        self.cmdtree[LIST] = self.cmdtree[BRIEF_HELP]
        if self.cmds:
            self.load(cmddict=self.cmds)

    def __del__(self):
        try:
            history_file = getattr(self, 'history_file')
            readline.write_history_file(history_file)
        except (AttributeError, FileNotFoundError):
            pass

    def load(self, cmdfile='', cmddict=None, cmdjson=''):
        """Load the JCmd command tree"""
        if cmddict:
            self.cmdtree.load_from_dict(cmddict)
        elif cmdfile:
            self.cmdtree.load_from_file(cmdfile)
        elif cmdjson:
            self.cmdtree.load_from_json(cmdjson)

    def _input_hook(self):
        """Input hook for adding a string to the new line."""
        if self.line:
            readline.insert_text(self.line)
            if not IS_WINDOWS:
                readline.redisplay()
            self.line = ''

    def cmdloop(self, prompt=None, intro=None):
        """Repeatedly issue a prompt, accept input, parse the input, and
        dispatch to execute the function or shell commands."""
        self.preloop()
        try:
            self.old_completer = readline.get_completer()
            readline.set_completer(self.complete)
            readline.parse_and_bind('tab: complete')
            if IS_WINDOWS:
                readline.parse_and_bind('?: "\C-alist \C-e\n"')
            else:
                readline.parse_and_bind('set comment-begin "? "')
                readline.parse_and_bind('?: insert-comment')
            delims = readline.get_completer_delims()
            delims = delims.replace('-', '')
            delims = delims.replace('.', '')
            delims = delims.replace('/', '')
            delims = delims.replace('~', '')
            delims = delims.replace('?', '')
            delims = delims.replace('!', '')
            readline.set_completer_delims(delims)
            readline.set_pre_input_hook(self._input_hook)
        except ImportError:
            self.stdout.write("Unable to initialize readline.")
        try:
            if intro is not None:
                self.intro = intro
            if self.intro:
                self.stdout.write(str(self.intro)+"\n")
            if prompt is not None:
                self.prompt = prompt
            stop = None
            while not stop:
                if self.cmdqueue:
                    line = self.cmdqueue.pop(0)
                else:
                    try:
                        line = input(self.prompt)
                    except EOFError:
                        line = EOF
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            self.postloop()
        finally:
            try:
                readline.set_completer(self.old_completer)
            except ImportError:
                pass

    def precmd(self, line):
        """Hook method executed just before the command dispatch."""
        return line

    def postcmd(self, stop, line):
        """Hook method executed just after a command dispatch is finished."""
        return stop

    def preloop(self):
        """Hook method before the cmdloop() is called."""
        pass

    def postloop(self):
        """Hook method after the cmdloop() returns"""
        pass

    @staticmethod
    def _parseline(line, begidx=-1, endidx=-1):
        """Parse the line of the input"""
        if begidx == -1 or endidx == -1:
            begidx = endidx = len(line)
        args = dict()
        incomplete = ''
        line = line[:endidx]
        words = shlex.split(line)
        for i, word in enumerate(words):
            spliter = word.find('=')
            if spliter >= 0:
                key = word[:spliter]
                value = word[spliter + 1:]
                vlist = value.split(',')
                if len(vlist) > 1:
                    args[key] = vlist
                else:
                    args[key] = value
                words[i] = word[:spliter]
        if begidx != endidx:
            incomplete = words[-1]
        if not line:
            return words, incomplete, args
        if line[-1] == '=' or line[-1] == ',':
            incomplete = words[-1]
        return words, incomplete, args

    @staticmethod
    def _next_word(cur_node, cur_word='', ignores=(), tail=''):
        """Return a list of next candidate nodes of the JCmd command tree."""
        try:
            clist = [c + tail for c in cur_node if
                     c.startswith(cur_word) and c not in COMPLETE_IGNORES and
                     c not in ignores]
        except (KeyError, AttributeError):
            return []
        else:
            return clist

    @staticmethod
    def _next_data(argtree, cur_arg, cur_data=''):
        """Return a list of next candidate data for argument completion."""
        if isinstance(cur_data, list):
            cur_data = cur_data[-1]
        try:
            argtype = argtree[cur_arg].get("type")
            argenum = argtree[cur_arg].get("enum")
            if argtype == "path":
                return list(glob.glob(cur_data + '*'))
            elif len(argenum):
                return [ each for each in argenum if each.startswith(cur_data) ]
        except BaseException:
            return [cur_data]

    def _complete_line(self, words, incomplete, args):
        """Return a list of next candidate completion string to readline."""
        cur_node = self.cmdtree
        remainder = words[:]
        remove = remainder.remove
        for index, word in enumerate(words):
            if incomplete and index + 1 == len(words):
                break
            try:
                cur_node = cur_node[word]
                remove(word)
                method = getattr(self, cur_node.complete)
                return method(remainder, incomplete)
            except KeyError:
                break
            except AttributeError:
                pass
            except BaseException:
                return []
        if not isinstance(cur_node, dict):
            return []
        get_next = JCmd._next_word
        if not remainder:
            nextwords = get_next(cur_node, tail=' ')
            if cur_node.eoc:
                nextwords += get_next(cur_node.args, tail='=')
            return nextwords
        # check cmds again
        elif incomplete:
            for word in remainder:
                nextwords = get_next(cur_node, word, tail=' ')
                if nextwords:
                    if cur_node.eoc:
                        nextwords += get_next(cur_node.args, word, tail='=')
                    return nextwords
                break
        # check args only
        if cur_node.eoc:
            ignores = set()
            for index, key in enumerate(remainder):
                if key not in cur_node.args:
                    return get_next(cur_node.args, key, ignores, tail='=')
                if key not in args:
                    return get_next(cur_node.args, key, ignores, tail='=')
                if incomplete == key:  # if empty
                    if not args[key]:
                        return JCmd._next_data(cur_node.args, key)
                    else:
                        return JCmd._next_data(cur_node.args, key, args[key])
                ignores.add(key)
            return get_next(cur_node.args, ignores=ignores, tail='=')
        return []

    def complete(self, text, state):
        """Return the next possible completion to readline library"""
        if state == 0:
            line = readline.get_line_buffer()
            begidx = readline.get_begidx()
            endidx = readline.get_endidx()
            words, incomplete, args = self._parseline(line, begidx, endidx)
            # print('\n', words, incomplete, args, '\n')
            self.completion_matches = self._complete_line(
                words, incomplete, args)
        try:
            return self.completion_matches[state]
        except IndexError:
            return None

    @staticmethod
    def check_range(argname, data, data_range):
        data_range = data_range.strip('<>')
        r = data_range.split('-')
        # print(int(r[0]), int(r[-1]), argname, int(data))
        if len(r) != 2:
            raise TypeError('invalid range type', argname)
        if int(r[0]) > int(data) or int(data) > int(r[-1]):
            raise ValueError('out of range:', argname, ":", data)
    
    @staticmethod
    def check_enum(argname, data, data_enum):
        if not isinstance(data_enum, list):
            raise TypeError('invalid enum type', argname)
        if data not in data_enum:
            raise ValueError('out of value:', argname, ":", data)

    def update_args(self, args, cmd_args):
        """fill out the arguments using the default value if not present."""
        # Set default value
        for key, value in cmd_args.items():
            try:
                data = args[key]
                r = value.get("range")
                if (r):
                    JCmd.check_range(key, data, r)
                e = value.get("enum")
                if (e):
                    JCmd.check_enum(key, data, e)
            except KeyError:
                try:
                    args[key] = value["default"]
                except KeyError:
                    raise KeyError(key)
        return args

    @staticmethod
    def format(origin, args):
        """Fill out the arguments to the command string."""
        updated = "%s" % (origin)
        front = origin.find("{{")
        while front >= 0:
            tail = origin.find("}}")
            if tail < 0:
                break
            key = origin[front + 2:tail]
            data = args[key]
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            elif not isinstance(data, str):
                data = str(data)
            updated = updated.replace(origin[front: tail + 2], data)
            origin = origin[tail + 2:]
            front = origin.find("{{")
        return updated

    def onecmd(self, line):
        """Execute the command"""
        if not line.strip():
            return self.end
        words, incomplete, args = self._parseline(line)
        cmd_index, cmd_node = self.cmdtree.find(words, bestmatch=True)

        # no command
        self.onecmd_line = line
        self.onecmd_words = words
        self.onecmd_args = args

        if not cmd_node.eoc:
            self.default()
            del self.onecmd_line
            del self.onecmd_words
            return self.end

        try:
            self.end = False
            args = self.update_args(args, cmd_node.args)
            self.onecmd_args = args

            if cmd_node.func:
                if not isinstance(cmd_node.func, list):
                    flist = [cmd_node.func]
                else:
                    flist = cmd_node.func
                for func in flist:
                    exec(func, globals(), args)
            elif cmd_node.shell:
                if not isinstance(cmd_node.shell, list):
                    slist = [cmd_node.shell]
                else:
                    slist = cmd_node.shell
                cmd_list = [self.format(shell, args) for shell in slist]
                cmd_str = ' && '.join(cmd_list)
                self.stdout.write('  shell: %s\n' % cmd_str)
                #subprocess.run(cmd_str, shell=True, check=True)
                subprocess.check_call(cmd_str, shell=True)
            elif cmd_node.method:
                method = getattr(self, cmd_node.method, self.default)
                # print("args:", args)
                method(**args)
            elif cmd_node.subtree:
                intro = cmd_node.subtree.get("intro")
                prompt = cmd_node.subtree.get("prompt")
                JCmd(cmdfile=cmd_node.subtree["file"]).cmdloop(prompt, intro)
        except AttributeError as ex:
            self.stdout.write("** No method or func: %s\n" % (ex))
        except KeyError as ex:
            self.stdout.write("** No argument: %s\n" % (ex))
        except BaseException as ex:
            self.stdout.write("** Failed: %s\n" % (ex))
        finally:
            # if getattr(self, "onecmd_line", None):
            del self.onecmd_line
            del self.onecmd_words
            del self.onecmd_args
        return self.end

    def default(self, **args):
        """for error messaging"""
        self.stdout.write('** Unknown cmd: %s\n' % self.onecmd_line)

    def complete_help(self, remainder, incomplete):
        """completion for help"""
        cur_pos = 0
        cur_node = self.cmdtree
        if incomplete:
            count = len(remainder) - 1
        else:
            count = len(remainder)
        for index in range(count):
            word = remainder[index]
            try:
                cur_pos = index + 1
                cur_node = cur_node[word]
            except BaseException:
                cur_pos = index
                break
        remainder = remainder[cur_pos:]
        if not isinstance(cur_node, dict):
            return cur_node
        if not remainder:
            nextwords = JCmd._next_word(cur_node, ignores=['help'], tail=' ')
            return nextwords
        for word in remainder:
            nextwords = JCmd._next_word(
                cur_node, word, ignores=['help'], tail=' ')
            if nextwords:
                return nextwords
            break
        return []

    def do_help(self):
        """show the command help in detail"""
        words = self.onecmd_words
        if len(words) > 1:
            targetwords = words[1:]
        else:
            targetwords = words
        target_index, target = self.cmdtree.find(targetwords, bestmatch=True)
        try:
            indent = self.indent_for_brief
            brief = True
            del self.indent_for_brief
        except AttributeError:
            indent = "  "
            brief = False
        if not brief:
            strlist = [
                '%s' % " ".join(targetwords[:target_index]),
                ':: %s' % target.__doc__]
            self.pprint(strlist)
        if target.eoc and len(target.args) > 0:
            strlist = list()
            strlist.append('>> Required Arguments')
            for k, value in target.args.items():
                if isinstance(value, JNode):
                    vstr = ' - %s: %s' % (k, value.__doc__)
                    if "default" in value:
                        vstr = vstr + ' (default:%s)' %(value["default"])
                    strlist.append(vstr)
                    if "range" in value:
                        strlist.append('   range(%s)' % (value["range"]))
                    if "enum" in value:
                        strlist.append('   enum(%s)' % (value["enum"]))
                else:
                    strlist.append(' - %s: %s' % (k, value))
            self.pprint(strlist, init_indent=indent, sub_indent=indent+'   ')

    def pprint(self, strsrc, init_indent='  ', sub_indent='  '):
        """print a string within the terminal width"""
        if not strsrc:
            return
        if not isinstance(strsrc, list):
            strsrc = [strsrc]
        tsize = shutil.get_terminal_size((80, 24))
        write = self.stdout.write
        for entry in strsrc:
            lines = textwrap.wrap(
                entry, width=tsize.columns,
                initial_indent=init_indent, subsequent_indent=sub_indent)
            for line in lines:
                write('%s\n' % line)

    def do_help_briefly(self, **args):
        """show the list of command helps"""
        line = self.onecmd_line
        words = self.onecmd_words
        # print(line, words)
        if line[-1] == ' ':
            targetwords = words[1:]
            lastword = ''
        else:  # incomplete
            targetwords = words[1:-1]
            lastword = words[-1]
        cur_index, cur_node = self.cmdtree.find(targetwords, bestmatch=True)
        keys = [
            key for key in cur_node if key.startswith(lastword) and
            key not in COMPLETE_IGNORES]
        if keys:
            if cur_node.eoc:
                keys.append("<cr>")
            max_len = max(map(len, keys), default=12)
            hstr = '{0:<%s}  {1}\n' % (max_len)
            strlist = list()
            for key in keys:
                try:
                    strlist.append(hstr.format(key, cur_node[key].__doc__))
                except KeyError:
                    strlist.append(hstr.format(key, cur_node.__doc__))
                    self.pprint(strlist)
                    strlist = list()
                    self.indent_for_brief = ' ' * (max_len + 4)
                    self.do_help()
            self.pprint(strlist)
        else:
            if cur_node.eoc:
                self.do_help()
        self.line = line.replace(LIST, "")
        self.line = line.replace(BRIEF_HELP, "")
        self.line = self.line.lstrip()
        if not IS_WINDOWS:
            pos = readline.get_current_history_length()
            readline.remove_history_item(pos - 1)

    def do_eof(self):
        """ctrl-d (end of JSON Command Interface)"""
        self.stdout.write("\n")
        self.end = True


if __name__ == "__main__":
    import os
    home = os.environ['HOME']
    try:
        FILENAME = sys.argv[1]
        JCmd(cmdfile=FILENAME, history=home + "/" + ".jcmdhistory").cmdloop()
    except IndexError:
        JCmd().cmdloop()
