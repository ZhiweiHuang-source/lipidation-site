# Utility Functions Directory

This directory contains reusable utility functions and helper modules used across multiple scripts and analyses.

## Common Utilities

### Sequence Processing
- FASTA file parsing and writing
- Sequence validation and cleaning
- Motif searching algorithms

### Data Management
- File I/O helpers
- Data format converters
- Configuration file parsers

### Visualization Helpers
- Custom plotting functions
- Color schemes for publications
- Figure export utilities

## Template Module

Example utility module structure:

```python
"""
Module: sequence_utils.py
Description: Utility functions for sequence analysis
"""

def parse_fasta(filename):
    """
    Parse a FASTA file and return sequences.
    
    Args:
        filename (str): Path to FASTA file
        
    Returns:
        dict: Dictionary of sequence_id: sequence
    """
    sequences = {}
    # Implementation here
    return sequences

def find_motif(sequence, motif):
    """
    Find all occurrences of a motif in a sequence.
    
    Args:
        sequence (str): Protein sequence
        motif (str): Motif pattern to search
        
    Returns:
        list: List of positions where motif occurs
    """
    positions = []
    # Implementation here
    return positions
```

## Usage

Import utilities in your scripts:
```python
from utils.sequence_utils import parse_fasta, find_motif
```

Place your reusable utility modules in this directory.
