# Lipidation Site Analysis Scripts

This repository contains custom scripts and macros used for lipidation site research projects. Lipidation is a post-translational modification where lipid molecules are covalently attached to proteins, affecting their localization, stability, and function.

## Repository Structure

- `scripts/` - Python/R scripts for sequence analysis and data processing
- `macros/` - ImageJ/Fiji macros for microscopy image analysis
- `analysis/` - Jupyter notebooks for data analysis and visualization
- `utils/` - Utility functions and helper scripts
- `docs/` - Documentation and protocols

## Getting Started

### Prerequisites

- Python 3.8+
- R 4.0+ (optional, for statistical analysis)
- ImageJ/Fiji (for microscopy analysis macros)
- Jupyter Notebook (for interactive analysis)

### Installation

```bash
# Clone the repository
git clone https://github.com/Wei0O/lipidation-site.git
cd lipidation-site

# Install Python dependencies (if requirements.txt exists)
pip install -r requirements.txt
```

## Usage

### Scripts

Place your custom Python or R scripts in the `scripts/` directory. Example:
```bash
python scripts/analyze_sequences.py --input data.fasta
```

### Macros

ImageJ/Fiji macros for image analysis should be placed in the `macros/` directory. To use:
1. Open ImageJ/Fiji
2. Go to Plugins > Macros > Run
3. Select the macro file from `macros/` directory

### Analysis Notebooks

Interactive Jupyter notebooks for exploratory data analysis are in the `analysis/` directory:
```bash
jupyter notebook analysis/
```

## Contributing

When adding new scripts or macros:
1. Place files in the appropriate directory
2. Include inline comments explaining the functionality
3. Update this README with usage instructions
4. Commit with descriptive messages

## License

This is a research repository. Please consult with the repository owner regarding usage and citation.

## Contact

For questions or collaborations, please open an issue or contact the repository maintainer. 
