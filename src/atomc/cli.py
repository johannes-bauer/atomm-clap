import sys
import typing
import getpass

def echo(value: str, stderr=False):
    if not stderr:
        print(value)
    else:
        print(value, file=sys.stderr)


def echo_sorted(values: typing.Sequence):
    echo(', '.join(sorted(values)))


def get_input(prompt: str, options=None):
    reply = None
    if prompt.rstrip()[-1] not in '?!:()':
        prompt = prompt.rstrip() + ':' + prompt[len(prompt.rstrip()):]
    if prompt.rstrip() == prompt:
        prompt += ' '
    while reply is None or (options and reply not in options):
        reply = input(prompt)
    return reply


def yes_no_question(prompt: str):
    reply = get_input(prompt, tuple('YNyn'))
    return reply.lower() == 'y'


def get_password(prompt: str):
    return getpass.getpass(prompt)


def error(value: str):
    echo(value)