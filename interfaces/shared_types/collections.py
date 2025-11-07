"""Collection-based shared types."""

from dataclasses import dataclass
from typing import TypeAlias, TypeGuard, assert_type


# Type aliases using Python 3.13 features
MatrixData: TypeAlias = list[list[float]]
Vector: TypeAlias = list[float]

@dataclass
class Matrix:
    """FFI-safe matrix representation."""

    rows: list[list[float]]

    @classmethod
    def from_rust(cls, rows: list[list[float]]) -> "Matrix":
        """Build a matrix from Rust data."""
        return cls(rows)

    def to_rust(self) -> list[list[float]]:
        """Return a Rust-friendly structure."""
        return self.rows
        
    def is_square(self) -> bool:
        """Check if the matrix is square."""
        if not self.rows:
            return True
        return all(len(row) == len(self.rows) for row in self.rows)
        
    @staticmethod
    def is_matrix_data(data: object) -> TypeGuard[MatrixData]:
        """Type guard to check if an object is valid matrix data."""
        if not isinstance(data, list):
            return False
        if not data:
            return True
        if not all(isinstance(row, list) for row in data):
            return False
        return all(all(isinstance(val, (int, float)) for val in row) for row in data)


# Example using assert_type from Python 3.13
def validate_matrix_example() -> None:
    """Example using Python 3.13 type checking features."""
    matrix_data = [[1.0, 2.0], [3.0, 4.0]]
    
    # Using TypeGuard
    if Matrix.is_matrix_data(matrix_data):
        matrix = Matrix(matrix_data)
        assert_type(matrix.rows, list[list[float]])
        
        # This would raise a type error if checked statically
        # assert_type(matrix.rows, list[str])  # Error
        
        result = matrix.to_rust()
        assert_type(result, MatrixData)
