#!/usr/bin/env python3
import numpy as np
from typing import Any, Sequence, Tuple, Union

class OffsetArray(Sequence):
    """
    <Example>
    arr: numpy.ndarray
    oa = OffsetArray(arr, (1,2))
    oa[i][j] == arr[i+2][j+1]
    >>> True
    """
    def __init__(self, array: np.ndarray, offset: Tuple[int, ...]):
        if len(array.shape)!=len(offset):
            raise ValueError("Dimension of array and offset doesn't match")
        self.array = array
        self.offset = offset

    def __len__(self) -> int:
        return len(self.array) - self.offset[0]

    def __getitem__(self, index: int) -> Union['OffsetArray', Any]:
        ret = self.array[index + self.offset[0]]
        if len(self.array.shape)==1:
            return ret
        else:
            return OffsetArray(ret, self.offset[1:])

    def __setitem__(self, index: int, value):
        self.array[index + self.offset[0]] = value
