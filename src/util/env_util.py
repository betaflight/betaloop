import os

def append_to_env(key: str, value: str):
    """append a value to an environment variable, creating the variable if it doesn't exist"""
    if key in os.environ:
        os.environ[key] += os.pathsep + value
    else:
        os.environ[key] = value