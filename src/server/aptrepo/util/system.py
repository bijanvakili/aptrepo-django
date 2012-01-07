import sys

def get_python_version():
    """
    Retrieves the python version as a float
    """
    return sys.version_info[0] + sys.version_info[1] * 0.1 + sys.version_info[2] * 0.01

def get_repository_version():
    """
    Returns the repository version as tuple
    """
    return ('0', '0', '1')
