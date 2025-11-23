#!/usr/bin/env python3
"""
Example Script: sequence_motif_finder.py
Description: Template for finding lipidation motifs in protein sequences
Author: [Your Name]
Date: [Date]

This is an example template. Modify it for your specific analysis needs.
"""

import argparse
import re
from pathlib import Path


def find_n_myristoylation_sites(sequence):
    """
    Find potential N-myristoylation sites.
    Motif: MGxxxS/T at N-terminus
    
    Args:
        sequence (str): Protein sequence
        
    Returns:
        list: List of positions where motif is found
    """
    motif_pattern = r'^MG...[ST]'
    matches = []
    
    if re.match(motif_pattern, sequence):
        matches.append({
            'type': 'N-myristoylation',
            'position': 0,
            'motif': sequence[:6]
        })
    
    return matches


def find_palmitoylation_sites(sequence):
    """
    Find potential palmitoylation sites (Cysteine residues).
    
    Args:
        sequence (str): Protein sequence
        
    Returns:
        list: List of cysteine positions
    """
    matches = []
    for i, aa in enumerate(sequence):
        if aa == 'C':
            matches.append({
                'type': 'Palmitoylation (Cys)',
                'position': i,
                'motif': sequence[max(0, i-2):min(len(sequence), i+3)]
            })
    
    return matches


def find_caax_box(sequence):
    """
    Find potential prenylation sites (CaaX box at C-terminus).
    
    Args:
        sequence (str): Protein sequence
        
    Returns:
        list: List of CaaX box matches
    """
    matches = []
    if len(sequence) >= 4:
        c_term = sequence[-4:]
        if c_term[0] == 'C':
            x = c_term[-1]
            # Farnesylation: X = M, S, Q, A
            # Geranylgeranylation: X = L, F
            if x in 'MSQALF':
                prenyl_type = 'Farnesylation' if x in 'MSQA' else 'Geranylgeranylation'
                matches.append({
                    'type': prenyl_type,
                    'position': len(sequence) - 4,
                    'motif': c_term
                })
    
    return matches


def analyze_sequence(seq_id, sequence):
    """
    Analyze a sequence for all lipidation sites.
    
    Args:
        seq_id (str): Sequence identifier
        sequence (str): Protein sequence
        
    Returns:
        dict: Analysis results
    """
    results = {
        'id': seq_id,
        'length': len(sequence),
        'n_myristoylation': find_n_myristoylation_sites(sequence),
        'palmitoylation': find_palmitoylation_sites(sequence),
        'prenylation': find_caax_box(sequence)
    }
    
    return results


def parse_fasta(fasta_file):
    """
    Simple FASTA parser.
    
    Args:
        fasta_file (str): Path to FASTA file
        
    Returns:
        dict: Dictionary of seq_id: sequence
    """
    sequences = {}
    current_id = None
    current_seq = []
    
    with open(fasta_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if current_id:
                    sequences[current_id] = ''.join(current_seq)
                current_id = line[1:].split()[0]
                current_seq = []
            else:
                current_seq.append(line)
        
        if current_id:
            sequences[current_id] = ''.join(current_seq)
    
    return sequences


def main():
    parser = argparse.ArgumentParser(
        description='Find potential lipidation sites in protein sequences'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Input FASTA file'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output file (TSV format)'
    )
    
    args = parser.parse_args()
    
    # Parse input sequences
    print(f"Reading sequences from {args.input}...")
    sequences = parse_fasta(args.input)
    print(f"Found {len(sequences)} sequences")
    
    # Analyze sequences
    print("Analyzing sequences for lipidation sites...")
    all_results = []
    
    for seq_id, sequence in sequences.items():
        results = analyze_sequence(seq_id, sequence)
        all_results.append(results)
    
    # Write results
    print(f"Writing results to {args.output}...")
    with open(args.output, 'w') as f:
        f.write("Sequence_ID\tLength\tModification_Type\tPosition\tMotif\n")
        
        for result in all_results:
            seq_id = result['id']
            length = result['length']
            
            # Write all modifications
            for mod_type in ['n_myristoylation', 'palmitoylation', 'prenylation']:
                for site in result[mod_type]:
                    f.write(f"{seq_id}\t{length}\t{site['type']}\t{site['position']}\t{site['motif']}\n")
    
    print("Analysis complete!")


if __name__ == '__main__':
    main()
