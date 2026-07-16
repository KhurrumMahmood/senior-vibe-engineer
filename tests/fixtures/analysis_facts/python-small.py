from pathlib import Path


def helper(item):
    return item


def convert(item):
    value = helper(item)
    return value


class Runner:
    def run(self, item):
        return convert(item)
