#!/usr/bin/env python3
"""Test script to verify the project structure."""
import sys
import os

# Add the project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from doi_extractor.db.models import Base, Paper
        print("✓ Models imported successfully")
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        return False
    
    try:
        from doi_extractor.parsers.crossref_parser import CrossrefParser
        print("✓ CrossrefParser imported successfully")
    except Exception as e:
        print(f"✗ CrossrefParser import failed: {e}")
        return False
    
    try:
        from doi_extractor.parsers.sci_journals import is_sci_journal
        print("✓ SCI journals module imported successfully")
    except Exception as e:
        print(f"✗ SCI journals import failed: {e}")
        return False
    
    try:
        from doi_extractor.parsers.cas_journals import is_cas_journal, get_cas_info
        print("✓ CAS journals module imported successfully")
    except Exception as e:
        print(f"✗ CAS journals import failed: {e}")
        return False
    
    try:
        from doi_extractor.extractor import DOIExtractor
        print("✓ DOIExtractor imported successfully")
    except Exception as e:
        print(f"✗ DOIExtractor import failed: {e}")
        return False
    
    return True

def test_parser():
    """Test the Crossref parser with sample data."""
    print("\nTesting parser...")
    
    from doi_extractor.parsers.crossref_parser import CrossrefParser
    
    # Sample Crossref API response
    sample_data = {
        "DOI": "10.1038/s41586-021-03819-2",
        "title": ["Sample Paper Title"],
        "author": [
            {"given": "John", "family": "Doe"},
            {"given": "Jane", "family": "Smith"}
        ],
        "published": {"date-parts": [[2021, 6, 15]]},
        "container-title": ["Nature"],
        "ISSN": ["0028-0836"],
        "abstract": "This is a sample abstract.",
        "URL": "https://doi.org/10.1038/s41586-021-03819-2",
        "is-referenced-by-count": 42
    }
    
    parser = CrossrefParser()
    result = parser.parse(sample_data)
    
    if result:
        print(f"✓ Parser works! Extracted: {result['title']}")
        print(f"  DOI: {result['doi']}")
        print(f"  Authors: {result['authors']}")
        print(f"  Journal: {result['journal']}")
        return True
    else:
        print("✗ Parser returned None")
        return False

def main():
    print("=" * 60)
    print("DOI Literature Extractor - Project Structure Test")
    print("=" * 60)
    
    success = True
    
    if not test_imports():
        success = False
    
    if not test_parser():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed")
    print("=" * 60)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
