from __future__ import annotations

import functools
import inspect
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
        self.matched: dict[str, typing.Any] = {}
        self.states: list[Subcommand] = []

    def transition(self, token, next_state):
        self.matched_tokens.append(token)
        self.matched[next_state._atomc_symbol] = next_state._atomc_convert_token(token, self)
        self.states.append(next_state)


def _un_keyword(token: str):
    assert isinstance(token, str)
    if token.endswith('_') and (keyword.iskeyword(token[:-1]) or token[:-1] in {'type', 'list'}):
        return token[:-1]
    else:
        return token


_symbols = set()
def symbol(name: str, unique=False):
    assert isinstance(name, str), name
    if unique:
        s = f'___unique_symbol_{name}_0000'
        i = 0
        while s in _symbols:
            s = f'{name}_{i:04d}'
            i += 1
        _symbols.add(s)
        return s
    else:
        _symbols.add(name)
        return name


def clear():
    """Clear all state.  Mainly used in tests."""
    global _symbols
    _symbols = set()


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
        symbol_unique: bool = True,
        arg_type: typing.Callable[[str], typing.Any] = None,
    ):
        self._successors: typing.Dict[str, FunctionalSubcommand] = {}
        self._atomc_wrapped = wrapped
        self._atomc_repetitions = repetitions
        self._atomc_suggestions = suggestions
        self._atomc_symbol = copied_from._atomc_symbol if copied_from else symbol(name, symbol_unique)
        self._atomc_name = name or target_token
        self._atomc_target_token = target_token
        self._atomc_executable = executable
        self._atomc_hidden = hidden
        self._atomc_description = description
        self._atomc_add_help_subcommand = add_help_subcommand
        self._atomc_arg_type = arg_type

        if add_help_subcommand:
            self.set_successor('-h', _help_short)
            self.set_successor('--help', _help_long)

    def set_successor(self, name: str, successor: FunctionalSubcommand):
        self._successors[name] = successor
        return successor

    def get_value(self, parser_state: ParserState):
        value = parser_state.matched.get(self._atomc_symbol, None)
        return value

    def __iadd__(self, other: FunctionalSubcommand):
        self._successors.update(other._successors)
        self._atomc_executable = other._atomc_executable
        return self

    def _atomc_transition(self, token, state: ParserState) -> FunctionalSubcommand:
        next_state = self._atomc_next_state(token, state)
        state.transition(token, next_state)
        return next_state

    def _atomc_next_state(self, token: str, state: ParserState) -> FunctionalSubcommand:
        candidates = list(self._successors.values())
        if self._atomc_repetitions == '+':
            candidates += [self]
        for handler in candidates:
            if handler._atomc_matches(token, state):
                return handler
        suggestions = ', '.join([
            s
            for handler in candidates
            for s in handler._atomc_next_token_suggestions(token, state)
        ])
        matched_tokens = ' '.join(state.matched_tokens)
        raise NoSuchSubcommandException(
            f"No match found for last token '{token}' after '{matched_tokens}'.  Suggestions: {suggestions}"
        )

    def _atomc_convert_token(self, token: str, state: ParserState):
        converted = self._atomc_arg_type(token) if self._atomc_arg_type else token
        if self._atomc_repetitions == 1:
            return converted
        elif self._atomc_repetitions == '+' and self._atomc_symbol in state.matched:
            return state.matched[self._atomc_symbol] + [converted]
        elif self._atomc_repetitions == '+':
            return [converted]
        else:
            raise ValueError(f"repetitions must be 1 or + but got {self._atomc_repetitions}.")

    def _atomc_this_token_suggestions(self, token: str, state: ParserState, only_cheap_suggestions: bool = False):
        tokens = []
        if isinstance(self._atomc_suggestions, list):
            tokens = [str(s) for s in self._atomc_suggestions]
        elif not only_cheap_suggestions and self._atomc_suggestions is not None:
            tokens = self._atomc_suggestions(token, state)
        elif self._atomc_target_token:
            tokens = [self._atomc_target_token]
        tokens = [t for t in tokens if t.startswith(token)]
        if (len(tokens) == 1) and (next_tokens := self._atomc_next_token_suggestions(tokens[0], state, True)):
            tokens = [
                tokens[0] + ' ' + nt for nt in next_tokens
            ]
        return tokens

    def _atomc_next_token_suggestions(self, token, state: ParserState, only_cheap_suggestions: bool = False):
        return [
            s
            for successor in self._successors.values()
            if not successor._atomc_hidden
            for s in successor._atomc_this_token_suggestions(token, state, only_cheap_suggestions)
        ]

    def _atomc_matches(self, token, state: ParserState) -> bool:
        return token == self._atomc_target_token

    def _atomc_is_final_state(self):
        return self._atomc_executable is not None

    def _atomc_execute(self, parser_state: ParserState):
        if self._atomc_is_final_state():
            self._atomc_executable(parser_state)
        else:
            raise ValueError("Not a final state.")

    def _atomc_print_help(self, prefix):
        if self._atomc_description:
            cli.echo(self._atomc_description, stderr=True)
        options = []
        def to_string(c):
            return f'[{c._atomc_name}]' if not c._atomc_target_token else c._atomc_target_token
        partial_options = [(o, prefix + to_string(o)) for o in self._successors.values()]
        while partial_options:
            _new_partial_options = []
            for option, option_string in partial_options:
                if len(option_string) < 70 and option._successors:
                    for s in option._successors.values():
                        if not s._atomc_hidden:
                            _new_partial_options.append([s, option_string + ' ' + to_string(s)])
                elif option._successors:
                    options.append(option_string + ' ...')

                if option._atomc_executable and not option._atomc_hidden:
                    options.append(option_string)
            partial_options = _new_partial_options
        options = '\n   '.join(sorted(set(options)))
        if options:
            if self._atomc_description:
                cli.echo('', stderr=True)
            cli.echo('Usage:', stderr=True)
            cli.echo('   ' + options, stderr=True)

    def __repr__(self):
        return f'subcommand({self._atomc_target_token})'

    def __call__(self, call=None, *args, **kwargs):
        if call is not None:
            if isinstance(call, _Call):
                self._atomc_executable = call
            else:
                self._atomc_executable = _Call(call, *(args))
        if 'suggestions' in kwargs:
            self._atomc_suggestions = kwargs['suggestions']

        if 'description' in kwargs:
            self._atomc_description = kwargs['description']
        elif call is not None and getattr(call, '__doc__', None) is not None:
            self._atomc_description = call.__doc__

        if 'hidden' in kwargs:
            self._atomc_hidden = kwargs['hidden']

def _print_help(parser_state: ParserState):
    parser_state.states[-2]._atomc_print_help(
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
        add_help_subcommand: bool = True,
        symbol_unique=True,
        arg_type: typing.Callable[[str], typing.Any] = None,
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
            symbol_unique,
            arg_type
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
            if item._atomc_symbol not in self._successors:
                self.__setattr__(item._atomc_symbol, item)
            return self.__getitem__(item._atomc_symbol)

    def __setitem__(self, key: str | Subcommand, value):
        logger.debug(f'setitem {key}, {value}')
        if isinstance(key, str):
            return self.__setattr__(key, value)
        else:
            return self.__setattr__(key._atomc_symbol, value)

    def copy(self):
        s = Subcommand(
            wrapped=self._atomc_wrapped,
            repetitions=self._atomc_repetitions,
            suggestions=self._atomc_suggestions,
            target_token=self._atomc_target_token,
            copied_from=self,
            name=self._atomc_name,
            executable=self._atomc_executable,
            description=self._atomc_description,
            add_help_subcommand=self._atomc_add_help_subcommand,
            hidden=self._atomc_hidden,
            arg_type=self._atomc_arg_type,
        )
        s._successors = dict(self._successors)
        return s

class Argument(Subcommand):
    def __init__(self, name, *args, **kwargs) -> None:
        kwargs['name'] = name
        kwargs['target_token'] = kwargs.get('target_token', None)
        super().__init__(*args, **kwargs, symbol_unique=False)

    def _atomc_matches(self, token: str, state: ParserState) -> bool:
        if self.__atomc_arg_type:
            try:
                self.__atomc_arg_type(token)
                return True
            except ValueError:
                return False
        return True

    def __repr__(self):
        return f'arg({self._atomc_name})'

    def copy(self):
        s = Argument(
            name=self._atomc_name,
            copied_from=self,
            repetitions=self._atomc_repetitions,
            wrapped=self._atomc_wrapped,
            suggestions=self._atomc_suggestions,
            target_token=self._atomc_target_token,
            executable=self._atomc_executable,
            arg_type=self.__atomc_arg_type,
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
            current_state = current_state._atomc_transition(token, parser_state)
    except NoSuchSubcommandException as e:
        error(str(e))
        return None

    if completion_mode:
        logger.debug(
            f"Completing item '{completable}', which is at index {completion_item_idx} "
            f"of original tokens {original_tokens}."
        )
        suggestions = current_state._atomc_next_token_suggestions(completable, parser_state)
        prefix = []

        while len(suggestions) == 1 and not current_state._atomc_is_final_state():
            prefix.append(suggestions[0])
            current_state = current_state._atomc_transition(suggestions[0], parser_state)
            suggestions = current_state._atomc_next_token_suggestions('', parser_state)

        if prefix:
            tokens = prefix
            if len(suggestions) == 1:
                tokens += suggestions
            print(' '.join([shlex.quote(t) for t in tokens]))
        else:
            line = '\n'.join(shlex.quote(s) for s in suggestions)
            print(line)
    else:
        current_state._atomc_execute(parser_state)


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
    def __init__(self, fn: typing.Callable, *args):
        self.fn = fn
        if args:
            self.args = args
            self.arg_names = []
        else:
            self.args = ()
            argspec = inspect.getfullargspec(fn)
            self.arg_names = argspec.args



    def __call__(self, matched: ParserState):
        args = []
        kwargs = {}
        if self.args:
            args = [
                arg.get_value(matched) if hasattr(arg, 'get_value') else arg
                for arg in self.args
            ]
        else:
            kwargs = {
                name: matched.matched[name]
                for name in self.arg_names
            }

        stargs = ', '.join(
            [str(a) for a in args]
            + [f'{key}={value}' for key, value in kwargs.items()]
        )

        logger.debug(f"Calling {self.fn.__name__}({stargs}, )")
        return self.fn(*args, **kwargs)
