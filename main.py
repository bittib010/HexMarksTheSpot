import logging
from abc import ABC, abstractmethod
from Artefacts.SQLiteFileParser import *
from Artefacts.JPEGFileParser import *
from Artefacts.MFTFileParser import *
from Artefacts.LNKFileParser import *
from common import Node, FileParser

logging.basicConfig(level=logging.INFO)

def get_file_parser(file):
    parsers = [SQLiteFileParser, JPEGFileParser, MFTFileParser, LNKFileParser]
    for Parser in parsers:
        print(Parser.recognizes(file))
        if Parser.recognizes(file):
            return Parser(file)
    raise UnknownFileTypeException("Unknown file type")


def print_node(node, indent=0):
    data_str = ' '.join(f'{byte:02x}' for byte in node.data)
    print(' ' * indent + node.info + data_str)
    for _, child in node.children:
        print_node(child, indent + 2)


def find_node(node, key):
    try:
        return node.search_child(key)
    except ValueError:
        return None

def main():
    try:
        with open("", "rb") as file: # enter your file here
            parser = get_file_parser(file)
            parser.validate(file)
            root = parser.parse()
            print_node(root)
    except Exception as e:
        logging.exception(str(e))

if __name__ == "__main__":
    main()
