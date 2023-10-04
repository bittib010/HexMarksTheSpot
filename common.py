from abc import ABC, abstractmethod
import random

class Node:
    def __init__(self, data, info, name=None, color=None, table_value=None):
        self.data = data
        self.info = info
        self.color = color if color else '#' + ''.join(["{:06x}".format(random.randint(0, 0xFFFFFF))])
        self.children = []
        self.name = name
        self.table_value = table_value  # or some default value


    def add_child(self, key, node):
        self.children.append((key, node))
        return node
    
    def add_more_description_content(self, more_info):
        self.info += more_info

    def search_child(self, key):
        for child_key, child_node in self.children:
            if child_key == key:
                return child_node
        raise ValueError(f"No child with key {key} found.")

class FileParser(ABC):
    def __init__(self, file):
        self.file = file

    @abstractmethod
    def parse(self):
        pass

    @classmethod
    @abstractmethod
    def recognizes(cls, file):
        pass

    @classmethod
    def validate(cls, file):
        if not cls.recognizes(file):
            # TODO: create exception
            raise InvalidFileException(f"File {file.name} is not a valid {cls.__name__} file")
