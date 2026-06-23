# Contributing to WOS

Thank you for considering contributing to Workspace OS!

## Contributor License Agreement (CLA)

**IMPORTANT**: Before your first contribution can be merged, you must sign the Contributor License Agreement (CLA). See [CLA.md](CLA.md) for details.

- **Individual contributors**: Add a comment to your first PR: "I have read and agree to the Contributor License Agreement (CLA.md)."
- **Corporate contributors**: Contact sergio.canales.e@gmail.com

## How to Contribute

### 1. Fork and Clone
```bash
git clone https://github.com/YOUR_USERNAME/workspace-os.git
cd workspace-os
```

### 2. Install Development Dependencies
```bash
pip install -e ".[dev]"
```

### 3. Create a Feature Branch
```bash
git checkout -b feat/your-feature-name
```

### 4. Make Your Changes

**Requirements**:
- Add copyright header to new files:
  ```python
  # Copyright 2026 Sergio Canales
  # SPDX-License-Identifier: Apache-2.0
  ```
- Write tests for new functionality
- Update documentation
- Follow existing code style

### 5. Run Tests
```bash
pytest
```

### 6. Submit a Pull Request

- Reference related issues
- Describe changes clearly
- Include test results
- Sign CLA if first contribution

## Code Standards

- **Type hints**: Required for all functions
- **Tests**: Required for new features
- **Docstrings**: Required for public APIs
- **Copyright**: Required in all new files

## Questions?

- GitHub Issues: Bug reports, feature requests
- Email: sergio.canales.e@gmail.com

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
