import sys

SHELL = None
EXECUTABLE_NAME = None

def add_completion_script_arguments(subcommand):
    from . import atomc
    import random

    global SHELL
    global EXECUTABLE_NAME
    if SHELL is None:
        SHELL = atomc.Argument('shell')
        EXECUTABLE_NAME = atomc.Argument('executable_name')

    def print_completion_script(shell: str, executable: str):
        """

        :param shell: for which shell to generate a script (currently only 'bash' supported)
        :param executable: the name to give the function that will call the script.
        :return:
        """
        import __main__
        suffix = str(random.randint(0,9999))
        if shell == 'bash':
            print(
f"""
function {executable} () {{
    export _ATOMC_EXECUTABLE_FUNCTION_NAME={executable};
    {sys.executable} {__main__.__file__} "$@"
}}

function _complete_{executable}_{suffix} {{
  readarray -t COMPREPLY <<< $("${{COMP_WORDS[@]}}" __atomm_clap__command_completion__ ${{COMP_CWORD}})
  return 0
}}
complete -F _complete_{executable}_{suffix} {executable}
"""
            )
        elif shell == 'zsh':
            print(
f"""
function {executable} () {{
    export _ATOMC_EXECUTABLE_FUNCTION_NAME={executable};
    {sys.executable} {__main__.__file__} "$@"
}}

function _{executable}_{suffix} {{
    local completions
    completions=("${{(@f)$("$words[@]" __atomm_clap__command_completion__ $((CURRENT - 1)))}}")
    compadd -a completions
}}
compdef _{executable}_{suffix} {executable}
"""
            )
        elif shell == 'fish':
            print(
f"""
function {executable}
    set -x _ATOMC_EXECUTABLE_FUNCTION_NAME {executable}
    {sys.executable} {__main__.__file__} $argv
end

function _{executable}_{suffix}
    set -l cmd (commandline -opc)
    set -l cur (commandline -ct)
    if test -z "$cur"
        {executable} $cmd '' __atomm_clap__command_completion__ (count $cmd)
    else
        {executable} $cmd __atomm_clap__command_completion__ (math (count $cmd) - 1)
    end
end
complete -c {executable} -f -a '(_{executable}_{suffix})'
"""
            )
        else:
            raise ValueError(f"Not implemented for shell '{shell}'")


    subcommand.completion(hidden=True)
    subcommand.completion[SHELL][EXECUTABLE_NAME](
        print_completion_script,
        SHELL,
        EXECUTABLE_NAME,
        hidden=True
    )
