# atomm-clap

**Almost Too Much Magic Command Line Argument Parser** — a Python library for
building deep, domain-specific CLIs whose command definitions read like a list
of example invocations.

---

## The idea

Most CLI parsers build a tree of flags and subcommands and then map that tree
onto function calls. atomm-clap works the other way around: you write the
command paths you want the user to type, and the library figures out the
routing.

```python
infra.server.by.nickname[SERVER].edit.config(handler, SERVER)
infra.server.by.nickname[SERVER].restart(handler, SERVER)
infra.deployment[DEPLOYMENT].add.probe.type_[TYPE].to.microscope[SCOPE](handler, ...)
```

This makes atomm-clap a good fit for **infrastructure tools, device managers,
and any CLI where the commands have a rich, noun-verb domain vocabulary** —
the kind of thing kubectl and the Docker CLI do, where commands read like 
sentences.  atomm-clap could, for example, easily implement

```bash
kubectl list <entity> in namespace <namespace> with label <label>
```

instead of
```bash
kubectl get pods -n <namespace> -l <label-key>=<label-value>
```

---

## Installation

```bash
pip install atomm-clap
```

Or from source:

```bash
git clone https://github.com/johannes-bauer/atomm-clap
cd atomm-clap
pip install -e .
```

---

## Quickstart

```python
#!/usr/bin/env python3
import sys
from atomc import CLI, parse_tokens, Argument

NAME = Argument('name')

cli = CLI('greeter')
cli.hello(lambda: print("Hello, world!"))
cli.hello.to[NAME](lambda n: print(f"Hello, {n}!"), NAME)

parse_tokens(cli, sys.argv)
```

```
$ greeter hello
Hello, world!

$ greeter hello to Alice
Hello, Alice!

$ greeter --help
Usage:
   greeter hello
   greeter hello to [name]
```

---

## Building a CLI

### Paths

A CLI is a `CLI` object. Attribute access on it creates subcommand nodes.
Calling a node registers a handler for that path:

```python
cli = CLI('mytool')
cli.server.list(list_servers)          # mytool server list
cli.server.restart(restart_server)     # mytool server restart
```

Handlers are plain callables with no arguments; values are passed explicitly
(see below).

### Arguments

`Argument` defines a positional capture node. It matches any token and records
the value. Use square-bracket syntax to place it in the path:

```python
SERVER = Argument('server')
PORT   = Argument('port', arg_type=int)

cli.server[SERVER].show(show_server, SERVER)          # mytool server <name> show
cli.server[SERVER].set.port[PORT](set_port, SERVER, PORT)  # mytool server <name> set port <n>
```

When a handler is called, `Argument` objects passed after the callable are
resolved to their matched values:

```python
def show_server(server_name):
    print(f"Showing {server_name}")

cli.server[SERVER].show(show_server, SERVER)
```

`arg_type` converts the raw string before passing it to the handler:

```python
COUNT = Argument('count', arg_type=int)
cli.run[COUNT].times(handler, COUNT)   # COUNT.get_value() returns an int
```

### Handlers can be plain functions or lambdas

```python
cli.status(lambda: print("OK"))

def do_deploy(env, version):
    ...

ENV     = Argument('env')
VERSION = Argument('version')
cli.deploy[ENV].version[VERSION](do_deploy, ENV, VERSION)
```

### Accessing matched values directly

From inside a handler that receives `parser_state`, call `ARG.get_value(parser_state)`:

```python
def handler(parser_state):
    server = SERVER.get_value(parser_state)
```

Argument objects passed as positional arguments after the callable (as shown
above) are the more common pattern — they let the library extract values and
pass them as ordinary function arguments.

---

## Shell completion

Every `CLI` automatically gains a hidden `completion` subcommand. Source the
output in your shell profile to enable tab completion.

### bash

```bash
# Creates the function 'mytool'.  Pass anything instead of 'mytool' to choose a different name.
eval "$(python path/to/my_tool/cli.py completion bash mytool)" 
```

Or add to `~/.bashrc`:

```bash
# Creates the function 'mytool'.  Pass anything instead of 'mytool' to choose a different name.
source <(python path/to/my_tool/cli.py completion bash mytool)
```

### zsh

```zsh
# Creates the function 'mytool'.  Pass anything instead of 'mytool' to choose a different name.
eval "$(python path/to/my_tool/cli.py completion zsh mytool)"
```

### fish

```fish
# Creates the function 'mytool'.  Pass anything instead of 'mytool' to choose a different name.
python path/to/my_tool/cli.py completion fish mytool | source
```

Or save to the completions directory:

```fish
# Creates the function 'mytool'.  Pass anything instead of 'mytool' to choose a different name.
python path/to/my_tool.py completion fish mytool > ~/.config/fish/completions/mytool.fish
```

The completion scripts invoke the tool itself with a special sentinel token,
so completion always reflects the live CLI definition — no separate completion
file to maintain.

---

## Help text

Every node responds to `--help` / `-h`. Descriptions can be provided as a
string or inferred from a function's docstring:

```python
cli.server(description="Manage servers")

def do_restart(server):
    """Restart the named server and wait for it to come back online."""
    ...

cli.server[SERVER].restart(do_restart, SERVER)
```

```
$ mytool server --help
Manage servers

Usage:
   mytool server <server> restart
   
$ mytool server "Some Server" restart --help
Restart the named server and wait for it to come back online.

Usage:
   mytool server <server> restart
```

---

## Example: bridge.py

`examples/bridge.py` is a self-contained starship bridge simulator that
demonstrates the patterns atomm-clap was built for: deep paths, named-entity
selection, two lookup routes to the same action, and optional mid-path
segments.

```
bridge status
bridge alert set red
bridge system sensors repair
bridge system shields set power 80
bridge shields raise
bridge engine engage warp 6
bridge weapon by type torpedo fire at target "Klingon Bird-of-Prey"
bridge weapon by type phaser status
bridge crew ranked "chief engineer" assign to system weapons
bridge crew named Reyes report
bridge scan for ships
bridge scan sector "12-A" for resources
bridge course plot to system "Alpha Centauri"
bridge log entry add "Encountered anomaly at bearing 270"
bridge log show
```

The CLI definition (excerpt) shows how the paths look in code:

```python
# Two lookup routes ("named" and "ranked") leading to the same actions
bridge.crew.named[CREW_NAME].report(cmd_crew_report_by_name, CREW_NAME)
bridge.crew.named[CREW_NAME].assign.to.system[SYSTEM](cmd_crew_assign_by_name, CREW_NAME, SYSTEM)
bridge.crew.ranked[CREW_RANK].report(cmd_crew_report_by_rank, CREW_RANK)
bridge.crew.ranked[CREW_RANK].assign.to.system[SYSTEM](cmd_crew_assign_by_rank, CREW_RANK, SYSTEM)

# "sector <X>" is optional — both forms route to the same handler
bridge.scan.for_.ships(cmd_scan_ships, SECTOR)
bridge.scan.for_.resources(cmd_scan_resources, SECTOR)
bridge.scan.sector[SECTOR].for_.ships(cmd_scan_ships, SECTOR)
bridge.scan.sector[SECTOR].for_.resources(cmd_scan_resources, SECTOR)

# Eight tokens deep
bridge.weapon.by.type_[WEAPON_TYPE].fire.at.target[TARGET](cmd_weapon_fire, WEAPON_TYPE, TARGET)
```

Run it with:

```bash
cd examples
PYTHONPATH=../src python3 bridge.py --help
```


# Hints

## Optional `--flag`s and `--option`s
atomm-clap treats the whole command line as one sentence in a DSL—the only distinction it makes between tokens is 
between `Subcommand`s and `Argument`s.  `--flags`- and `--option`-like patterns can be implemented within that framework:

### Implement `--flag`s:

```python
### CLI DEFINITION
def tell_me_about_frogs(everything):
    if not everything:
        assert everything is None
        print("Oh, where do I even start!")
    else:
        assert everything == '--everything'
        print("Really, everything?")
        
tell = CLI('tell')
tell.me.about.frogs(tell_me_about_frogs, tell.me['--everything'])
tell.me['--everything'].about = tell.me.about
```

The `+=` operator merges one node's successors and executable into another,
creating an optional segment in the path.

```bash
### SHELL USAGE 
$ tell me about frogs
Oh, where do I even start!

$ tell me --everything about frogs
Really, everything?
```

### Implement `--option OPTIONAL_ARGUMENT`:
```python
### CLI DEFINITION
counting = CLI('counting')

SEVEN = Argument('seven')

def did_it(seven):
    if not seven:
        print('Skroob: Six? What happened to eight and seven?')
    elif seven not in ['seven', '7']:
        print(f"{seven}?!?")
    else:
        print("Computer: ... five, four, three, two, one.  Have a nice day.\nEverybody: Thank you!")

counting.down.ten.nine.six(did_it, SEVEN)
counting.down.ten.nine['--eight'][SEVEN] += counting.down.ten.nine
```

```bash
### SHELL USAGE
$ counting down ten nine six
Skroob: Six? What happened to eight and seven?

$ counting down ten nine --eight whatever six
whatever?!?

$ counting down ten nine --eight seven six
Computer: ... five, four, three, two, one.  Have a nice day.
Everybody: Thank you!
```

## Python reserved words

Some Python keywords appear naturally in CLI paths. Append `_` to use them;
atomm-clap strips it from the matched token:

| Write | Matches |
|-------|---------|
| `cli.list_` or `cli.for_` | `list`, `for` |
| `cli.type_` | `type` |
| `cli.raise_` | `raise` |

```python
cli.scan.for_.ships(scan_ships)   # mytool scan for ships
cli.alert.raise_(sound_alarm)     # mytool alert raise
```

### Reserved attribute names

A handful of names are instance attributes of the node class and cannot be
used as path tokens via attribute access: `name`, `description`, `symbol`,
`executable`, `hidden`. The most commonly encountered one is `name`.

Use a synonym (`named`, `nickname`, `callsign`, `id`) or subscript syntax as
a workaround:

```python
# This silently returns the string 'by', not a subcommand node:
cli.server.by._atomc_name[SERVER]  # ← WRONG

# Use a synonym instead:
cli.server.by.nickname[SERVER]  # ← OK
cli.server.named[SERVER]  # ← OK

# Or subscript syntax (less readable):
cli.server.by['name'][SERVER]  # ← OK
```

## Decorators
Some of the popular commandline parser libraries provide functionality to add decorators to functions to turn those
functions into CLI commands.  atomm-clap accidentally provides limited support for this pattern:

```python
### CLI DEFINITION

decorated = CLI('beautiful')

@decorated.function
def dec_fun():
    print("I'm pretty!")
```

That said, the idea behind atomm-clap is to define a CLI as one readable list of command patterns that can be checked 
quickly by a developer to understand a CLI's capabilities and find entrypoints into the actual application.
A source code file with many non-trivial, decorated functions arguably doesn't serve that purpose as well as a sequence
of command definitions.

It will often also introduce performance issues, see [below](#Performance). 


## Performance
One of the most useful features of atomm-clap are its automatic `--help` text generation and commandline completion.
Especially the latter is useful only if it is fast.  If, however, the cli script itself loads an entire application,
and especially if that leads to heavy libraries like `tensorflow` or similar to be loaded just to provide one
suggestion or print a help message, then that becomes a lot less fun.

It's therefore recommended to separate CLI definition, API definition, and application:

```python
## api.py
## Note: no imports on the top level.

def get_servers(cluster):
    """Prints the servers on the given cluster."""
    from my_application.kubernetes_app import get_servers as _get_servers
    servers = _get_servers(cluster)
    print(', '.join(servers))


def print_gpus():
    """Prints the GPUs that are currently available."""
    import tensorflow as tf # This can take half a second
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print('Have GPUs:')
        print(gpus)
        return True
    else:
        print("No GPUs found")
        return False
```

```python
## cli.py
import api

from atomc import CLI, parse_tokens, Argument

CLUSTER = Argument('cluster')

my_tool = CLI('my_tool')

my_tool.print.servers.for_[CLUSTER](api.get_servers, CLUSTER)
my_tool.print.gpus(api.get_gpus)
```

The following will return without loading anything from the actual application or from tensorflow:
```bash
$ my_tool print gpus --help
Prints the GPUs that are currently available.
```

Personally, we think separating concerns like this is a good pattern anyway.

## Printing and Logging
atomm-clap makes heavy use of Python's standard logging facility. 
In normal operation, it sets its own log level to `logging.ERROR` so its logs don't clutter the user application's 
output.
atomm-clap's log level can be set explicitly (`DEBUG`, `INFO`, ...) using the environment variable
`_ATOMC_OTHER_LOG_LEVELS`.

In commandline completion mode, atomm-clap sets the global log level to `logging.ERROR`, so application output doesn't
clutter the completion.  However, atomm-clap does not control `print()` statements, so if there are any `print()`
statements in the code that execute through imports, then the output of those `print()` statements will be treated as
completion items by the shell.

That should not happen, though, if the code is split into CLI definition, API definition, and application, as 
recommended under [Performance](#Performance), above. 
