# Contributing Guidelines

Thank you for contributing to the lipidation-site repository! This document provides guidelines for organizing and documenting your custom scripts and macros.

## Repository Organization

### Directory Structure

```
lipidation-site/
├── scripts/          # Python/R analysis scripts
├── macros/           # ImageJ/Fiji macros
├── analysis/         # Jupyter notebooks
├── utils/            # Reusable utility functions
├── docs/             # Documentation and protocols
└── requirements.txt  # Python dependencies
```

## Adding New Scripts

### Python Scripts

1. **Location**: Place in `scripts/` directory
2. **Naming**: Use descriptive, lowercase names with underscores (e.g., `analyze_palmitoylation_sites.py`)
3. **Structure**: Include the following elements:

```python
#!/usr/bin/env python3
"""
Script Name: your_script_name.py
Description: Brief description of what the script does
Author: Your Name
Date: YYYY-MM-DD
"""

import argparse

def main():
    parser = argparse.ArgumentParser(description='Your script description')
    # Add arguments
    args = parser.parse_args()
    # Your code here

if __name__ == '__main__':
    main()
```

4. **Documentation**: 
   - Include docstrings for all functions
   - Add inline comments for complex logic
   - Provide usage examples in the script header

5. **Dependencies**: Add any new Python packages to `requirements.txt`

### R Scripts

1. **Location**: Place in `scripts/` directory
2. **Naming**: Use descriptive names (e.g., `statistical_analysis.R`)
3. **Header**: Include metadata at the top:

```r
# Script Name: your_script.R
# Description: What this script does
# Author: Your Name
# Date: YYYY-MM-DD

# Load required libraries
library(tidyverse)
```

### ImageJ Macros

1. **Location**: Place in `macros/` directory
2. **Extension**: Use `.ijm` extension
3. **Header**: Include comments at the top:

```javascript
// Macro Name: your_macro.ijm
// Description: What this macro does
// Author: Your Name
// Date: YYYY-MM-DD
//
// Usage instructions here
```

4. **User Interaction**: Use `waitForUser()` for interactive steps
5. **Output**: Print results to Log window using `print()`

## Adding Analysis Notebooks

1. **Location**: Place in `analysis/` directory
2. **Naming**: Use numbered prefixes for ordering (e.g., `01_data_exploration.ipynb`)
3. **Structure**:
   - Start with markdown cell explaining the notebook's purpose
   - Include clear section headers
   - Document each analysis step
   - Include interpretation of results

4. **Best Practices**:
   - Clear outputs before committing: `jupyter nbconvert --clear-output *.ipynb`
   - Keep notebooks focused on specific analyses
   - Save final figures to a `figures/` subdirectory

## Adding Utility Functions

1. **Location**: Place in `utils/` directory
2. **Purpose**: Reusable functions used across multiple scripts
3. **Documentation**: Include comprehensive docstrings with examples

```python
def your_function(param1, param2):
    """
    Brief description.
    
    Args:
        param1 (type): Description
        param2 (type): Description
        
    Returns:
        type: Description
        
    Example:
        >>> your_function('input', 42)
        'expected output'
    """
    pass
```

## Documentation

### Adding Protocols

1. **Location**: Place in `docs/` directory
2. **Format**: Markdown (`.md`) files
3. **Content**: 
   - Step-by-step procedures
   - Required materials/software
   - Expected outcomes
   - Troubleshooting tips

### Updating README

When adding significant new functionality:
1. Update the main `README.md` 
2. Add usage examples
3. Update the repository structure section if needed

## Code Quality

### Python

- Follow PEP 8 style guidelines
- Use meaningful variable names
- Keep functions focused and modular
- Handle errors gracefully with try/except
- Validate input arguments

### R

- Follow tidyverse style guide
- Use `<-` for assignment
- Use meaningful variable names
- Comment complex operations

### ImageJ Macros

- Use clear variable names
- Comment major steps
- Provide user feedback with `print()` statements
- Handle edge cases (e.g., no image open)

## Testing

Before committing:

1. **Test your script**: Run with sample data
2. **Check dependencies**: Ensure all required packages are listed
3. **Verify documentation**: Make sure usage instructions are clear
4. **Review output**: Confirm results are as expected

## Commit Messages

Write clear, descriptive commit messages:

- Good: "Add script for identifying N-myristoylation sites"
- Good: "Fix bug in palmitoylation site detection regex"
- Bad: "Update"
- Bad: "Fixed stuff"

## Questions or Issues?

If you have questions about contributing or encounter issues:
1. Check existing documentation in `docs/`
2. Review example scripts in each directory
3. Open an issue for discussion

Thank you for your contributions!
