from __future__ import annotations

import functools
import keyword
import typing
import shlex
import logging

from . import cli
from .cli import error

logger = logging.getLogger(__name__)


class ParserState:
    def __init__(self):
        self.matched_tokens = []
        self.matched: dict[str, Subcommand] = {}
        self.states: list[Subcommand] = []

    def transition(self, token, next_state):
        self.matched_tokens.append(token)
        self.matched[next_state.symbol] = next_state.convert_token(token, self)
        self.states.append(next_state)


def _un_keyword(token: str):
    assert isinstance(token, str)
    if token.endswith('_') and (keyword.iskeyword(token[:-1]) or token[:-1] in {'type', 'list'}):
        return token[:-1]
    else:
        return token


_symbols = set()
def symbol(name: str):
    assert isinstance(name, str), name
    s = f'{name}_0000'
    i = 0
    while s in _symbols:
        s = f'{name}_{i:04d}'
        i += 1
    _symbols.add(s)
    return s

class FunctionalSubcommand:
    def __init__(
        self,
        wrapped=None,
        repetitions: str|int = 1,
        suggestions: typing.Callable | list = None,
        target_token: str | None = None,
        copied_from=None,
        name: str = None,
        executable: typing.Callable = None,
        hidden = False,
        description: str | None = None,
        add_help_subcommand: bool = True,
    ):
        self._successors: typing.Dict[str, FunctionalSubcommand] = {}
        self.wrapped = wrapped
        self.repetitions = repetitions
        self.suggestions = suggestions
        self.symbol = copied_from.symbol if copied_from else symbol(name)
        self.name = name or target_token
        self.target_token = target_token
        self.executable = executable
        self.hidden = hidden
        self.description = description
        self.add_help_subcommand = add_help_subcommand

        if add_help_subcommand:
            self.set_successor('-h', _help_short)
            self.set_successor('--help', _help_long)

    def set_successor(self, name: str, successor: FunctionalSubcommand):
        self._successors[name] = successor
        return successor

    def get_value(self, parser_state: ParserState):
        value = parser_state.matched.get(self.symbol, None)
        return value

    def __iadd__(self, other: FunctionalSubcommand):
        self._successors.update(other._successors)
        self.executable = other.executable
        return self

    def transition(self, token, state: ParserState) -> FunctionalSubcommand:
        next_state = self.next_state(token, state)
        state.transition(token, next_state)
        return next_state

    def next_state(self, token: str, state: ParserState) -> FunctionalSubcommand:
        candidates = list(self._successors.values())
        if self.repetitions == '+':
            candidates += [self]
        for handler in candidates:
            if handler.matches(token, state):
                return handler
        suggestions = ', '.join([
            s
            for handler in candidates
            for s in handler.next_token_suggestions(token, state)
        ])
        matched_tokens = ' '.join(state.matched_tokens)
        raise NoSuchSubcommandException(
            f"No match found for last token '{token}' after '{matched_tokens}'.  Suggestions: {suggestions}"
        )

    def convert_token(self, token: str, state: ParserState):
        if self.repetitions == 1:
            return token
        elif self.repetitions == '+' and self.symbol in state.matched:
            return state.matched[self.symbol] + [token]
        elif self.repetitions == '+':
            return [token]
        else:
            raise ValueError(f"repetitions must be 1 or + but got {self.repetitions}.")

    def this_token_suggestions(self, token: str, state: ParserState, only_cheap_suggestions: bool = False):
        tokens = []
        if isinstance(self.suggestions, list):
            tokens = [str(s) for s in self.suggestions]
        elif not only_cheap_suggestions and self.suggestions is not None:
            tokens = self.suggestions(token, state)
        elif self.target_token:
            tokens = [self.target_token]
        tokens = [t for t in tokens if t.startswith(token)]
        if (len(tokens) == 1) and (next_tokens := self.next_token_suggestions(tokens[0], state, True)):
            tokens = [
                tokens[0] + ' ' + nt for nt in next_tokens
            ]
        return tokens

    def next_token_suggestions(self, token, state: ParserState, only_cheap_suggestions: bool = False):
        return [
            s
            for successor in self._successors.values()
            if not successor.hidden
            for s in successor.this_token_suggestions(token, state, only_cheap_suggestions)
        ]

    def matches(self, token, state: ParserState) -> bool:
        return token == self.target_token

    def is_final_state(self):
        return self.executable is not None

    def execute(self, parser_state: ParserState):
        if self.is_final_state():
            self.executable(parser_state)
        else:
            raise ValueError("Not a final state.")

    def print_help(self, prefix):
        if self.description:
            cli.echo(self.description, stderr=True)
        options = []
        def to_string(c):
            return f'[{c.name}]' if not c.target_token else c.target_token
        partial_options = [(o, prefix + to_string(o)) for o in self._successors.values()]
        while partial_options:
            _new_partial_options = []
            for option, option_string in partial_options:
                if len(option_string) < 70 and option._successors:
                    for s in option._successors.values():
                        if not s.hidden:
                            _new_partial_options.append([s, option_string + ' ' + to_string(s)])
                elif option._successors:
                    options.append(option_string + ' ...')

                if option.executable and not option.hidden:
                    options.append(option_string)
            partial_options = _new_partial_options
        options = '\n   '.join(sorted(set(options)))
        if options:
            if self.description:
                cli.echo('', stderr=True)
            cli.echo('Usage:', stderr=True)
            cli.echo('   ' + options, stderr=True)

    def __repr__(self):
        return f'subcommand({self.target_token})'

    def __call__(self, call=None, *args, **kwargs):
        if call is not None:
            if isinstance(call, _Call):
                self.executable = call
            else:
                self.executable = _Call(call, *(args))
        if 'suggestions' in kwargs:
            self.suggestions = kwargs['suggestions']

        if 'description' in kwargs:
            self.description = kwargs['description']
        elif call is not None and getattr(call, '__doc__', None) is not None:
            self.description = call.__doc__

        if 'hidden' in kwargs:
            self.hidden = kwargs['hidden']

def _print_help(parser_state: ParserState):
    parser_state.states[-2].print_help(
        ' '.join(parser_state.matched_tokens[:-1]) + ' '
    )

_help_short = FunctionalSubcommand(
    name = 'help_short',
    target_token = '-h',
    executable = _print_help,
    hidden = True,
    add_help_subcommand = False
)

_help_long = FunctionalSubcommand(
    name = 'help_long',
    target_token = '--help',
    executable = _print_help,
    hidden = True,
    add_help_subcommand = False
)

class Subcommand(FunctionalSubcommand):
    def __init__(self,
        wrapped=None,
        repetitions=1,
        suggestions: typing.Callable | list = None,
        target_token: str | None = None,
        copied_from=None,
        name: str = None,
        executable: typing.Callable = None,
        hidden = False,
        description: str | None = None,
        add_help_subcommand: bool = True
    ):
        super().__init__(
            wrapped,
            repetitions,
            suggestions,
            target_token,
            copied_from,
            name,
            executable,
            hidden,
            description,
            add_help_subcommand,
        )
        self._initialized = True

    def __setattr__(self, name, value):
        if hasattr(self, '_initialized') and name not in self.__dict__:
            logger.debug(f"making {value} a subcommand of {self} with name {name}")
            if hasattr(value, 'copy'):
                logger.debug(f'{value} will be copied.')
                value = value.copy()
            elif hasattr(value, '__call__'):
                logger.debug(f'{value} is callable and wrapped in a Subcommand.')
                value = Subcommand(target_token=name, executable=value)
            else:
                logger.debug(f'{value} is neither copyable nor callable; using it as-is.')
            assert isinstance(name, str), name
            self.set_successor(name, value)
        else:
            self.__dict__[name] = value

    def __getattr__(self, item):
        if not item.startswith('_'): # in particular: not '_initialized'
            item = _un_keyword(item)
            if item not in self._successors:
                logger.debug(
                    f"'{item}' is not yet a subcommand of '{self}'.  Creating a default successor with that name."
                )
                self._successors[item] = self.default_successor(item)
            return self._successors[item]
        else:
            # __getattribute__ must have been tried if we get here---the property isn't there.
            raise AttributeError(item)

    def default_successor(self, name):
        name = _un_keyword(name)
        return Subcommand(name=name, target_token=name)

    def __contains__(self, item):
        return item in self._successors

    def __getitem__(self, item: str | Subcommand):
        if isinstance(item, str):
            return self.__getattr__(item)
        else:
            if item.symbol not in self._successors:
                self.__setattr__(item.symbol, item)
            return self.__getitem__(item.symbol)

    def __setitem__(self, key: str | Subcommand, value):
        logger.debug(f'setitem {key}, {value}')
        if isinstance(key, str):
            return self.__setattr__(key, value)
        else:
            return self.__setattr__(key.symbol, value)

    def copy(self):
        s = Subcommand(
            wrapped=self.wrapped,
            repetitions=self.repetitions,
            suggestions=self.suggestions,
            target_token=self.target_token,
            copied_from=self,
            name=self.name,
            executable=self.executable,
            description=self.description,
            add_help_subcommand=self.add_help_subcommand,
            hidden=self.hidden
        )
        s._successors = dict(self._successors)
        return s

class Argument(Subcommand):
    def __init__(self, name, *args, arg_type: typing.Callable[[str], typing.Any]=None, **kwargs) -> None:
        kwargs['name'] = kwargs.get('name', name)
        kwargs['target_token'] = kwargs.get('target_token', None)
        self.arg_type = arg_type
        super().__init__(*args, **kwargs)

    def get_value(self, parser_state: ParserState):
        value = super().get_value(parser_state)
        if self.arg_type:
            value = self.arg_type(value)
        return value

    def matches(self, token: str, state: ParserState) -> bool:
        if self.arg_type:
            try:
                self.arg_type(token)
                return True
            except ValueError:
                return False
        return True

    def __repr__(self):
        return f'arg({self.name})'

    def copy(self):
        s = Argument(
            name=self.name,
            copied_from=self,
            repetitions=self.repetitions,
            wrapped=self.wrapped,
            suggestions=self.suggestions,
            target_token=self.target_token,
            executable=self.executable,
            arg_type=self.arg_type,
        )
        s._successors = dict(self._successors)
        return s


def parse_tokens(inital_state: Subcommand, tokens: list[str]):
    import os
    completion_mode = len(tokens) > 2 and tokens[-2] == '__atomm_clap__command_completion__'
    completion_item_idx = int(tokens[-1]) if completion_mode else None
    original_tokens = tokens
    completable, tokens = (
        (tokens[completion_item_idx], tokens[1:completion_item_idx])
        if completion_mode
        else (None, tokens[1:])
    )

    if '_ATOMC_LOG_LEVEL' in os.environ:
        other_level = os.environ.get('_ATOMC_OTHER_LOG_LEVELS', 'DEBUG')
        logging.basicConfig(level=other_level)
        logger.setLevel(os.environ['_ATOMC_LOG_LEVEL'])
    else:
        if completion_mode:
            logging.basicConfig(level=logging.ERROR)
        logger.setLevel(logging.ERROR)

    if '_ATOMC_EXECUTABLE_FUNCTION_NAME' in os.environ:
        executable = os.environ['_ATOMC_EXECUTABLE_FUNCTION_NAME']
    else:
        import sys
        import __main__
        executable = sys.executable + ' ' + __main__.__file__

    parser_state = ParserState()
    parser_state.transition(executable, inital_state)
    current_state = inital_state

    try:
        for token in tokens:
            current_state = current_state.transition(token, parser_state)
    except NoSuchSubcommandException as e:
        error(str(e))
        return None

    if completion_mode:
        logger.debug(
            f"Completing item '{completable}', which is at index {completion_item_idx} "
            f"of original tokens {original_tokens}."
        )
        suggestions = current_state.next_token_suggestions(completable, parser_state)
        prefix = []

        while len(suggestions) == 1 and not current_state.is_final_state():
            prefix.append(suggestions[0])
            current_state = current_state.transition(suggestions[0], parser_state)
            suggestions = current_state.next_token_suggestions('', parser_state)

        if prefix:
            tokens = prefix
            if len(suggestions) == 1:
                tokens += suggestions
            print(' '.join([shlex.quote(t) for t in tokens]))
        else:
            line = '\n'.join(shlex.quote(s) for s in suggestions)
            print(line)
    else:
        current_state.execute(parser_state)


def call(fn, *args):
    @functools.wraps(fn)
    def function(matched: dict[Subcommand, list[typing.Any]]):
        arguments = [
            arg.get_value(matched) if hasattr(arg, 'get_value') else arg
            for arg in args
        ]
        stargs = ', '.join([str(a) for a in arguments])
        logger.debug(f"Calling {fn.__name__}({stargs})")
        return fn(*arguments)
    return function


def suggest_from(fn, *args):
    @functools.wraps(fn)
    def function(token, parser_state: ParserState):
        arguments = [
            arg.get_value(parser_state.matched) if hasattr(arg, 'get_value') else arg
            for arg in args
        ]
        stargs = ', '.join([str(a) for a in arguments])
        logger.debug(f"Calling {fn.__name__}({stargs})")
        suggestions = fn(*arguments)
        return [s for s in suggestions if s.startswith(token)]
    return function


class ProxyArgument:
    def __init__(self, name, func):
        self.name = name
        self.func = func

    def get_value(self, matched: dict[Subcommand, list[typing.Any]]):
        return self.func(matched)


class NoSuchSubcommandException(Exception):
    pass

class _Call:
    def __init__(self, fn, *args):
        self.fn = fn
        self.args = args

    def __call__(self, matched: dict[Subcommand, list[typing.Any]]):
        arguments = [
            arg.get_value(matched) if hasattr(arg, 'get_value') else arg
            for arg in self.args
        ]
        stargs = ', '.join([str(a) for a in arguments])
        logger.debug(f"Calling {self.fn.__name__}({stargs})")
        return self.fn(*arguments)
