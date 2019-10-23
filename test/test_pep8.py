

import os
import subprocess

# directory names whose children should not be checked
IGNORED_DIRS = (".git")

# file names that should be checked even though they do not end in .py
EXTRA_FILES = ()


def check(files):
    """
    Check all files that files yields for pep8 errors.

    Args:
        file: a generator yielding strings referring to files to check

    Returns:
        False if there are errors, else True
    """

    # E501: Line too long
    # E303: Too many blank lines
    args = ["pycodestyle", "--ignore", "W605,E501,E303,E305,E302,E402"] + list(files)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    if len(out) != 0:
        print(out)
    if len(err) != 0:
        print(err)
    return not len(out) and not len(err)


def _find_files_to_test():
    current_dir = os.path.dirname(os.path.realpath(__file__))
    parent = os.path.join(current_dir, "..")
    for r, d, files in os.walk(parent):
        for ignored in IGNORED_DIRS:
            if ignored in d:
                d.remove(ignored)
        for dir_ in d:
            if dir_.startswith('.'):
                d.remove(dir_)
        for f in files:
            if f[0] == '.':
                continue
            if f.endswith('.py') or f in EXTRA_FILES:
                yield os.path.join(r, f)


def test_pep8():
    assert check(_find_files_to_test()), "Found pep8 errors! (see logs below)"
