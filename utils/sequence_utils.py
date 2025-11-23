"""
Sequence Utility Functions
Module for common sequence processing tasks in lipidation research
"""

def parse_fasta(fasta_file):
    """
    Parse a FASTA file and return sequences.
    
    Args:
        fasta_file (str or Path): Path to FASTA file
        
    Returns:
        dict: Dictionary mapping sequence_id to sequence string
        
    Example:
        >>> sequences = parse_fasta('proteins.fasta')
        >>> len(sequences)
        150
    """
    sequences = {}
    current_id = None
    current_seq = []
    
    with open(fasta_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('>'):
                # Save previous sequence
                if current_id is not None:
                    sequences[current_id] = ''.join(current_seq)
                
                # Start new sequence
                current_id = line[1:].split()[0]
                current_seq = []
            else:
                # Append to current sequence
                current_seq.append(line.upper())
        
        # Don't forget the last sequence
        if current_id is not None:
            sequences[current_id] = ''.join(current_seq)
    
    return sequences


def write_fasta(sequences, output_file):
    """
    Write sequences to a FASTA file.
    
    Args:
        sequences (dict): Dictionary of sequence_id: sequence
        output_file (str or Path): Output file path
        
    Example:
        >>> seqs = {'seq1': 'MGKSKSK', 'seq2': 'MVKSKCC'}
        >>> write_fasta(seqs, 'output.fasta')
    """
    with open(output_file, 'w') as f:
        for seq_id, sequence in sequences.items():
            f.write(f">{seq_id}\n")
            # Write sequence in lines of 60 characters
            for i in range(0, len(sequence), 60):
                f.write(sequence[i:i+60] + '\n')


def validate_sequence(sequence, allow_ambiguous=False):
    """
    Validate that a sequence contains only valid amino acid codes.
    
    Args:
        sequence (str): Protein sequence
        allow_ambiguous (bool): Allow ambiguous amino acids (B, Z, X)
        
    Returns:
        bool: True if valid, False otherwise
        
    Example:
        >>> validate_sequence('MGKKSKC')
        True
        >>> validate_sequence('MGKK123')
        False
    """
    valid_aa = set('ACDEFGHIKLMNPQRSTVWY')
    if allow_ambiguous:
        valid_aa.update('BZX')
    
    return all(aa in valid_aa for aa in sequence.upper())


def get_sequence_window(sequence, position, window_size=5):
    """
    Extract a window of amino acids around a specific position.
    
    Args:
        sequence (str): Protein sequence
        position (int): Center position (0-indexed)
        window_size (int): Number of residues on each side
        
    Returns:
        str: Sequence window (padded with '-' if at sequence ends)
        
    Example:
        >>> seq = 'MGKKKSKRTCDE'
        >>> get_sequence_window(seq, 5, 3)
        'KKSKRTC'
    """
    start = max(0, position - window_size)
    end = min(len(sequence), position + window_size + 1)
    
    window = sequence[start:end]
    
    # Pad if at sequence boundaries
    if start == 0 and position < window_size:
        window = '-' * (window_size - position) + window
    if end == len(sequence) and position + window_size >= len(sequence):
        window = window + '-' * (position + window_size - len(sequence) + 1)
    
    return window


def calculate_hydrophobicity(sequence, scale='kyte_doolittle'):
    """
    Calculate average hydrophobicity of a sequence.
    
    Args:
        sequence (str): Protein sequence
        scale (str): Hydrophobicity scale to use
        
    Returns:
        float: Average hydrophobicity score
        
    Example:
        >>> calculate_hydrophobicity('MGKKSKCC')
        -0.75
    """
    # Kyte-Doolittle hydrophobicity scale
    kyte_doolittle = {
        'A': 1.8, 'C': 2.5, 'D': -3.5, 'E': -3.5, 'F': 2.8,
        'G': -0.4, 'H': -3.2, 'I': 4.5, 'K': -3.9, 'L': 3.8,
        'M': 1.9, 'N': -3.5, 'P': -1.6, 'Q': -3.5, 'R': -4.5,
        'S': -0.8, 'T': -0.7, 'V': 4.2, 'W': -0.9, 'Y': -1.3
    }
    
    if scale == 'kyte_doolittle':
        scale_dict = kyte_doolittle
    else:
        raise ValueError(f"Unknown hydrophobicity scale: {scale}")
    
    scores = [scale_dict.get(aa, 0) for aa in sequence.upper()]
    return sum(scores) / len(scores) if scores else 0.0


def find_sequence_motif(sequence, motif_regex):
    """
    Find all occurrences of a regex motif in a sequence.
    
    Args:
        sequence (str): Protein sequence
        motif_regex (str): Regular expression pattern
        
    Returns:
        list: List of (start_position, matched_sequence) tuples
        
    Example:
        >>> find_sequence_motif('MGCKKCKDE', 'C..C')
        [(2, 'CKKC')]
    """
    import re
    matches = []
    for match in re.finditer(motif_regex, sequence.upper()):
        matches.append((match.start(), match.group()))
    return matches
