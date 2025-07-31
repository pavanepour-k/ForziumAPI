"""Input validation helpers"""

from typing import List


def validate_matrix(matrix: List[List[float]]) -> None:
    """Validate that the matrix is non-empty and rectangular"""
    if not matrix or not all(len(row) == len(matrix[0]) for row in matrix):
        raise ValueError("Data must be a non-empty rectangular matrix")