#!/usr/bin/env python3
# neoul@ymail.com
"""
Json Command Interface library
A generic class to build line-oriented command interpreters.
"""

import sys
import string
import json
import glob
import shlex
import subprocess
import time

# [TBD] readline is not supported on windows.
# Use pyreadline instead ...
import readline

__all__ = ["JCmd"]

PROMPT = 'jcmd> '
IDENTCHARS = string.ascii_letters + string.digits + '_'

LOG_FILENAME = 'jcmd.log'

CMD = "cmd"
ARGS = "args"
HELP = "help"
NO_HELP = "no help"
FUNC = "func"
SHELL = "shell"
SUBTREE = "subtree"
EXEC_SHELL = "!"
BRIEF_HELP = "?"
EOF = "EOF"
COMPLETE = "complete"
COMPLETE_IGNORES = set([EXEC_SHELL, BRIEF_HELP, EOF])


class JNode(dict):
    """Json Command Interface Node"""

    def __init__(self, *args, **kargs):
        self.func = None
        self.shell = None
        self.subtree = None
        self.complete = None
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
        """internal method for update arguments"""
        for key, value in self.args.items():
            if not isinstance(value, dict):
                self.args[key] = JNode({"help":value})

    def load_from_dict(self, dic):
        """load Json Command Interface node from a dictionary"""
        jdata = json.dumps(dic)
        self.load_from_json(jdata)

    def load_from_json(self, jdata):
        """load Json Command Interface node from json string"""
        def hooker(dic):
            """hooker for loading Json Command Interface."""
            return JNode(dic)
        self.update(json.loads(jdata, object_hook=hooker))

    def load_from_file(self, cmdfile=None):
        """load Json Command Interface node from json file"""
        with open(cmdfile, "r") as cfile:
            self.load_from_json(cfile.read())

    def find(self, jnodes=(), bestmatch=False):
        """find a Json Command interface node"""
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
    """Json Command Line interface
    A simple framework for writing line-oriented command interpreters."""

    identchars = IDENTCHARS

    intro = "\n [Json Command Line Interface]\n"
    completion_matches = list()
    use_rawinput = True
    end = False
    line = ''

    def __init__(
            self, completekey='tab', stdin=None, stdout=None, **kargs):
        """Instantiate a Json Command Line Interface."""

        self.prompt = PROMPT
        self.cmdtree = JNode()
        if stdin is not None:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin
        if stdout is not None:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout
        self.cmdqueue = []
        self.completekey = completekey

        try:
            self.cmdtree.load_from_file(kargs["cmdfile"])
        except (FileNotFoundError, json.decoder.JSONDecodeError) as ex:
            self.stdout.write("%s\n" % ex)
        except KeyError as ex:
            pass

        # Built-in commands
        self.cmdtree[EOF] = JNode({
            HELP: "quit jcmd (ctrl+d)",
            CMD: {FUNC: "self.do_eof()"}})
        self.cmdtree['quit'] = self.cmdtree[EOF]
        self.cmdtree[EXEC_SHELL] = JNode({
            HELP: "execute a shell command",
            CMD: {SHELL: "{{shell-cmd}}"},
            ARGS: {"shell-cmd": "executable shell command"}})
        self.cmdtree[HELP] = JNode({
            HELP: "show a command help",
            CMD: {
                FUNC: "self.do_help(words)",
                COMPLETE: "self.complete_help(remainder, incomplete)"
            }
        })
        self.cmdtree[BRIEF_HELP] = JNode({
            HELP: "show all the commands' help briefly",
            CMD: {
                FUNC: "self.do_help_briefly(line, words)",
                COMPLETE: "self.complete_help(remainder, incomplete)"
            }
        })

    def load(self, cmdfile='', cmddict=None, cmdjson=''):
        if cmddict:
            self.cmdtree.load_from_dict(cmddict)
        elif cmdfile:
            self.cmdtree.load_from_file(cmdfile)
        elif cmdjson:
            self.cmdtree.load_from_json(cmdjson)

    def _input_hook(self):
        "Input hook for adding a string to the line."
        if self.line:
            readline.insert_text(self.line)
            readline.redisplay()
            self.line = ''

    def cmdloop(self, prompt=None, intro=None):
        """Repeatedly issue a prompt, accept input, parse an initial prefix
        off the received input, and dispatch to action methods, passing them
        the remainder of the line as argument.
        """
        self.preloop()
        if self.use_rawinput and self.completekey:
            try:
                self.old_completer = readline.get_completer()
                readline.set_completer(self.complete)
                readline.parse_and_bind(self.completekey+": complete")
                readline.parse_and_bind('set comment-begin "? "')
                readline.parse_and_bind('?: insert-comment')
                delims = readline.get_completer_delims()
                delims = delims.replace('-', '')
                delims = delims.replace('.', '')
                delims = delims.replace('=', '')
                delims = delims.replace('/', '')
                delims = delims.replace('~', '')
                delims = delims.replace('?', '')
                delims = delims.replace('!', '')
                readline.set_completer_delims(delims)
                readline.set_pre_input_hook(self._input_hook)
            except ImportError:
                self.stdout.write("Unable to initialize readline.")
                pass
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
                    if self.use_rawinput:
                        try:
                            line = input(self.prompt)
                        except EOFError:
                            line = EOF
                    else:
                        self.stdout.write(self.prompt)
                        self.stdout.flush()
                        line = self.stdin.readline()
                        if not len(line):
                            line = EOF
                        else:
                            line = line.rstrip('\r\n')
                line = self.precmd(line)
                stop = self.onecmd(line)
                stop = self.postcmd(stop, line)
            self.postloop()
        finally:
            if self.use_rawinput and self.completekey:
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
        "Hook method before the cmdloop() is called."
        pass

    def postloop(self):
        "Hook method after the cmdloop() returns"
        pass

    def parseline(self, line, begidx=-1, endidx=-1):
        """Parse the line"""
        if begidx == -1 or endidx == -1:
            begidx = endidx = len(line)
        args = dict()
        incomplete = ''
        line = line[:endidx]
        words = shlex.split(line)
        if begidx != endidx:
            incomplete = words[-1]
        for i, word in enumerate(words):
            spliter = word.find('=')
            if spliter >= 0:
                args[word[:spliter]] = word[spliter + 1:]
                words[i] = word[:spliter]
        return words, incomplete, args

    @staticmethod
    def _next_words(cur_node, cur_word='', ignores=(), tail=''):
        """list of next nodes in cmdtree"""
        try:
            clist = [c + tail for c in cur_node if
                     c.startswith(cur_word) and c not in COMPLETE_IGNORES and
                     c not in ignores]
        except (KeyError, AttributeError):
            return []
        else:
            return clist

    @staticmethod
    def _next_data(argtree, cur_arg, cur_data):
        """list of next data in a argument completion"""
        try:
            argtype = argtree[cur_arg]["type"]
            if argtype == "path":
                return list(map(
                    lambda a: cur_arg + '=' + a,
                    glob.glob(cur_data + '*')))
        except BaseException:
            return [cur_arg + '=' + cur_data]

    def completeline(self, words, incomplete, args):
        """JCmd parse command"""
        cur_node = self.cmdtree
        remainder = words[:]
        remove = remainder.remove
        for index, word in enumerate(words):
            if incomplete and index + 1 == len(words):
                break
            try:
                cur_node = cur_node[word]
                remove(word)
                if cur_node.complete:
                    return eval(cur_node.complete, locals=locals())
            except KeyError:
                break
            except AttributeError:
                pass
            except BaseException as ex:
                return []
        if not isinstance(cur_node, dict):
            return []
        get_next = self._next_words
        if not remainder:
            nextwords = get_next(cur_node, tail=' ')
            if cur_node.eoc:
                nextwords += get_next(cur_node.args, tail='=')
            return nextwords
        # check cmds again
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
            for index, word in enumerate(remainder):
                nextargs = get_next(
                    cur_node.args, word, ignores, tail='=')
                if not nextargs:
                    return []
                if incomplete.startswith(word):
                    if word in args:
                        return self._next_data(cur_node.args, word, args[word])
                    return nextargs
                ignores.add(word)
            nextargs = get_next(
                cur_node.args, ignores=ignores, tail='=')
            return nextargs
        return []

    def complete(self, text, state):
        """Return the next possible completion for 'text'."""
        if state == 0:
            line = readline.get_line_buffer()
            begidx = readline.get_begidx()
            endidx = readline.get_endidx()
            words, incomplete, args = self.parseline(line, begidx, endidx)
            self.completion_matches = self.completeline(
                words, incomplete, args)
        try:
            return self.completion_matches[state]
        except IndexError:
            return None

    @staticmethod
    def updateargs(input_args, cmd_args):
        """Update defaults"""
        output_args = dict()
        for key, value in cmd_args.items():
            try:
                output_args[key] = value["default"]
            except KeyError:
                pass
            try:
                output_args[key] = input_args[key]
            except KeyError:
                pass
        return output_args

    def onecmd(self, line):
        """Execute the command"""
        if not line.strip():
            return self.end
        words, incomplete, args = self.parseline(line)
        cmd_index, cmd_node = self.cmdtree.find(words, bestmatch=True)

        # no command
        if not cmd_node.eoc:
            return self.default(line)

        self.end = False
        if cmd_node.func:
            try:
                exec(cmd_node.func, globals(), locals())
            except KeyError as ex:
                self.stdout.write("  No argument: %s\n" % (ex))
            except BaseException as ex:
                self.stdout.write("  Failed: %s\n" % (ex))
        elif cmd_node.shell:
            try:
                inputs = self.updateargs(args, cmd_node.args)
                if not isinstance(cmd_node.shell, list):
                    slist = [cmd_node.shell]
                else:
                    slist = cmd_node.shell
                cmd_list = [shell.format(**inputs) for shell in slist]
                for cmd_str in cmd_list:
                    self.stdout.write('  shell: %s\n' % cmd_str)
                    subprocess.run(cmd_str, shell=True, check=True)
            except KeyError as ex:
                self.stdout.write("  No argument: %s\n" % (ex))
            except BaseException as ex:
                self.stdout.write("  Failed: %s\n" % (ex))
        elif cmd_node.subtree:
            try:
                intro = cmd_node.subtree.get("intro")
                prompt = cmd_node.subtree.get("prompt")
                JCmd(cmdfile=cmd_node.subtree["file"]).cmdloop(prompt, intro)
            except BaseException as ex:
                self.stdout.write("  Failed: %s\n" % (ex))
        return self.end

    def default(self, line):
        """Called on an input line when the command prefix is not recognized.
        If this method is not overridden, it prints an error message and
        returns."""
        self.stdout.write('*** Unknown syntax: %s\n'%line)

    def complete_help(self, remainder, incomplete):
        """completion function for help"""
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
            except BaseException as ex:
                cur_pos = index
                break
        remainder = remainder[cur_pos:]
        if not isinstance(cur_node, dict):
            return cur_node
        for word in remainder:
            nextwords = self._next_words(
                cur_node, word, ignores=['help'], tail=' ')
            if nextwords:
                return nextwords
            break
        if not remainder:
            nextwords = self._next_words(cur_node, ignores=['help'], tail=' ')
            return nextwords
        return []

    def do_help(self, words):
        """show the command help"""
        targetwords = words[1:]
        if not targetwords:
            targetwords = words
        target_index, target = self.cmdtree.find(targetwords, bestmatch=True)
        self.stdout.write('  %s\n' % " ".join(targetwords[:target_index]))
        self.stdout.write('  %s\n' % target.__doc__)
        if target.eoc:
            if len(target.args) > 0:
                self.stdout.write('  required arguments:\n')
            for k, value in target.args.items():
                if isinstance(value, JNode):
                    self.stdout.write('   - %s: %s\n' % (k, value.__doc__))
                else:
                    self.stdout.write('   - %s: %s\n' % (k, value))

    def do_help_briefly(self, line, words):
        """show the list of command helps"""
        if line[-1] == ' ':
            targetwords = words[1:]
            lastword = ''
        else:
            targetwords = words[1:-1]
            lastword = words[-1]
        cur_index, cur_node = self.cmdtree.find(targetwords, bestmatch=True)
        keys = [
            key for key in cur_node if key.startswith(lastword) and
            key not in COMPLETE_IGNORES]
        if keys:
            max_len = max(map(len, keys), default=12)
            max_len_doc = 74 - max_len
            hstr = '  {0:<%s}  {1}\n' % (max_len)
            for key in keys:
                self.stdout.write(
                    hstr.format(key, cur_node[key].__doc__[:max_len_doc]))
        else:
            if cur_node.eoc:
                words[0] = HELP
                self.do_help(words[:cur_index+1])
        self.line = line.replace("? ", "")
        pos = readline.get_current_history_length()
        readline.remove_history_item(pos - 1)

    def do_eof(self):
        """ctrl-d (end of Json Command Interface)"""
        self.stdout.write("\n")
        self.end = True


if __name__ == "__main__":
    try:
        argv = sys.argv[1]
        JCmd(cmdfile=argv).cmdloop()
    except IndexError:
        JCmd().cmdloop()
