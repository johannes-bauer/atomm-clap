def test_smoketest():
    from atomc import CLI, parse_tokens

    smoketest = CLI('smoketest')

    did_it = [False]
    def doit():
        did_it[0] = True


    smoketest.some.command(
        call=doit
    )
    parse_tokens(smoketest, ['smoke', 'some', 'command'])

    assert did_it[0]


def test_simple_variables():
    from atomc import CLI, parse_tokens, Argument

    RED = Argument('red')
    BLUE = Argument('blue')

    one = CLI('one')

    called_width = []
    def did_it(*args):
        called_width.extend(args)

    one.fish.two.fish[RED].fish[BLUE].fish(
        did_it,
        RED,
        BLUE
    )

    parse_tokens(one, ['one', 'fish', 'two', 'fish', 'ReD', 'fish', 'BlUe', 'fish'])

    assert called_width == ['ReD', 'BlUe']


def test_converted_variables():
    from atomc import CLI, parse_tokens, Argument

    TWO = Argument('two', arg_type=int)
    RED = Argument('red')
    BLUE = Argument('blue')

    one = CLI('one')

    called_width = []

    def did_it(*args):
        called_width.extend(args)

    one.fish[TWO].fish[RED].fish[BLUE].fish(
        did_it,
        TWO,
        RED,
        BLUE
    )

    parse_tokens(one, ['one', 'fish', '2', 'fish', 'ReD', 'fish', 'BlUe', 'fish'])

    assert called_width == [2, 'ReD', 'BlUe']


def test_bash_completion():
    from atomc import CLI, parse_tokens, Argument

    one = CLI('one')
    one.two()

    parse_tokens(one, ['executable_name', 'completion', 'bash', 'some_executable'])


def test_bash_builds_friendly_function(capsys):

    import sys
    import __main__
    from atomc import CLI, parse_tokens

    one = CLI('one')
    one.two()

    the_executable_name = 'some_friendly_executable_name'
    parse_tokens(one, ['executable_name', 'completion', 'bash', the_executable_name])


    expected_script = (
f"""
function {the_executable_name} () {{
    export _ATOMC_EXECUTABLE_FUNCTION_NAME={the_executable_name};
    {sys.executable} {__main__.__file__} "$@"
}}
""")

    assert expected_script in capsys.readouterr().out


def test_zsh_builds_friendly_function(capsys):

    import sys
    import __main__
    from atomc import CLI, parse_tokens

    one = CLI('one')
    one.two()

    the_executable_name = 'some_friendly_executable_name'
    parse_tokens(one, ['executable_name', 'completion', 'zsh', the_executable_name])

    out = capsys.readouterr().out
    assert f'function {the_executable_name} ()' in out
    assert f'export _ATOMC_EXECUTABLE_FUNCTION_NAME={the_executable_name}' in out
    assert f'{sys.executable} {__main__.__file__} "$@"' in out
    assert f'compdef' in out
    assert f'compadd' in out
    assert '__atomm_clap__command_completion__' in out
    assert '$((CURRENT - 1))' in out
    assert '$words[@]' in out


def test_fish_builds_friendly_function(capsys):

    import sys
    import __main__
    from atomc import CLI, parse_tokens

    one = CLI('one')
    one.two()

    the_executable_name = 'some_friendly_executable_name'
    parse_tokens(one, ['executable_name', 'completion', 'fish', the_executable_name])

    out = capsys.readouterr().out
    assert f'function {the_executable_name}' in out
    assert f'set -x _ATOMC_EXECUTABLE_FUNCTION_NAME {the_executable_name}' in out
    assert f'{sys.executable} {__main__.__file__} $argv' in out
    assert 'complete -c' in out
    assert '__atomm_clap__command_completion__' in out
    assert 'commandline -opc' in out
    assert 'commandline -ct' in out


def test_help_prints_description(capsys):
    from atomc import CLI, parse_tokens, Argument

    one = CLI('one')
    one.two(description='three, four')

    parse_tokens(one, ['executable_name', 'two', '--help'])

    assert 'three, four' in capsys.readouterr().err


def test_help_prints_docstring(capsys):
    from atomc import CLI, parse_tokens, Argument

    def the_function():
        """This is a function with a docstring"""
        pass

    one = CLI('one')
    one.two(the_function)

    parse_tokens(one, ['executable_name', 'two', '--help'])

    assert 'This is a function with a docstring' in capsys.readouterr().err


def test_help_prints_usage(capsys, monkeypatch):
    monkeypatch.setenv('_ATOMC_EXECUTABLE_FUNCTION_NAME', 'executable_name')

    from atomc import CLI, parse_tokens

    def dummy():
        pass

    one = CLI('one')
    one.two.three(call=dummy)

    parse_tokens(one, ['executable_name', '--help'])

    assert 'two three' in capsys.readouterr().err

def test_help_prints_previously_matched(capsys, monkeypatch):
    monkeypatch.setenv('_ATOMC_EXECUTABLE_FUNCTION_NAME', 'executable_name')

    from atomc import CLI, parse_tokens

    def dummy():
        pass

    one = CLI('one')
    one.two.three(call=dummy)

    parse_tokens(one, ['two', '--help'])

    assert 'two three' in capsys.readouterr().err


def test_completion_completes_second_final_token(capsys):
    from atomc import CLI, parse_tokens

    def dummy():
        pass

    one = CLI('one')
    one.two(call=dummy)

    parse_tokens(one, ['1', 'tw', '__atomm_clap__command_completion__', '1'])

    assert capsys.readouterr().out == 'two\n'


def test_completion_completes_fourth_final_token(capsys):
    from atomc import CLI, parse_tokens

    def dummy():
        pass

    one = CLI('one')
    one.two.three.four.five.six.seven(call=dummy)

    parse_tokens(one, ['1', 'two', 'three', 'four', 'five', 'six', 's', '__atomm_clap__command_completion__', '6'])

    assert capsys.readouterr().out == 'seven\n'

def test_completion_completes_empty_token(capsys):
    from atomc import CLI, parse_tokens

    def dummy():
        pass

    one = CLI('one')
    one.two(call=dummy)

    parse_tokens(one, ['1', '', '__atomm_clap__command_completion__', '1'])

    assert capsys.readouterr().out == 'two\n'


def test_completion_completes_multiple_tokens(capsys):
    from atomc import CLI, parse_tokens

    def dummy():
        pass

    one = CLI('one')
    one.two.three.four(call=dummy)

    parse_tokens(one, ['1', '', '__atomm_clap__command_completion__', '1'])

    assert capsys.readouterr().out == 'two three four\n'


def test_optional_subcommands_are_optional():
    from atomc import CLI, parse_tokens

    giving = CLI('giving')

    called_width = []

    def did_it(*args):
        called_width.extend(args)

    giving.up.is_['--not'].an.option(did_it, giving.up.is_['--not'])
    giving.up.is_ += giving.up.is_['--not']

    parse_tokens(giving, ['giving', 'up', 'is', 'an', 'option'])
    assert called_width == [None]

    called_width = []
    parse_tokens(giving, ['giving', 'up', 'is', '--not', 'an', 'option'])
    assert called_width == ['--not']


def test_optional_dash_dash_arguments_are_optional():
    from atomc import CLI, parse_tokens, Argument

    ARGH = Argument('ARGH')

    one = CLI('one')

    called_width = []

    def did_it(*args):
        called_width.extend(args)

    one.two.three.four(did_it, ARGH)
    one.two['--intermission'][ARGH] += one.two

    parse_tokens(one, ['one', 'two', 'three', 'four'])
    assert called_width == [None]

    called_width = []
    parse_tokens(one, ['one', 'two', '--intermission', 'value', 'three', 'four'])
    assert called_width == ['value']


def test_decorator():
    from atomc import CLI, parse_tokens, Argument

    decorated = CLI('beautiful')

    called = [0]

    @decorated.function
    def did_it():
        called[0] += 1

    parse_tokens(decorated, ['decorated', 'function'])
    assert called == [1]
