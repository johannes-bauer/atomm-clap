from .atomc import (
    parse_tokens,
    Argument,
    ProxyArgument,
    Subcommand
)

from .completion import add_completion_script_arguments as _add_completion_script_arguments

class CLI(Subcommand):
    def __init__(self, name, *args, **kwargs) -> None:
        super().__init__(*args, target_token=None, name=name, **kwargs)
        _add_completion_script_arguments(self)
