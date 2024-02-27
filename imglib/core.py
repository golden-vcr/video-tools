from enum import Enum
from dataclasses import dataclass


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int


class Align(Enum):
    START = 1
    MIDDLE = 2
    END = 3

    @classmethod
    def parse(cls, v: str) -> 'Align':
        return {
           'start': cls.START, 
           'middle': cls.MIDDLE,
           'end': cls.END,
        }[v]


setattr(Align, 'choices', [v.name.lower() for v in Align])
