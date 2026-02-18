import sys
import os
import re

# Add src/backend to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
backend_path = os.path.join(project_root, "src", "backend")
sys.path.append(backend_path)

try:
    from app.services.prompt_templates import validate_xml_output
except ImportError as e:
    print(f"Failed to import validate_xml_output: {e}")
    sys.exit(1)

def test_validate_xml_output_valid():
    response = "<thinking>foo</thinking><answer>bar</answer><confidence>HIGH</confidence>"
    assert validate_xml_output(response, ["thinking", "answer", "confidence"]) is True
    print("test_validate_xml_output_valid PASSED")

def test_validate_xml_output_markdown_block():
    response = "```xml\n<thinking>foo</thinking><answer>bar</answer><confidence>HIGH</confidence>\n```"
    assert validate_xml_output(response, ["thinking", "answer", "confidence"]) is True
    print("test_validate_xml_output_markdown_block PASSED")

def test_validate_xml_output_case_mismatch():
    response = "<Thinking>foo</Thinking><Answer>bar</Answer><Confidence>HIGH</Confidence>"
    assert validate_xml_output(response, ["thinking", "answer", "confidence"]) is True
    print("test_validate_xml_output_case_mismatch PASSED")

def test_validate_xml_output_mixed_case():
    response = "<Thinking>foo</thinking>"
    # This currently passes with our regex logic because we check opening and closing separately
    # and we check order.
    # <Thinking> matches opening
    # </thinking> matches closing
    # Order is correct.
    assert validate_xml_output(response, ["thinking"]) is True
    print("test_validate_xml_output_mixed_case PASSED")

def test_validate_xml_output_attributes():
    response = '<thinking type="deep">foo</thinking>'
    assert validate_xml_output(response, ["thinking"]) is True
    print("test_validate_xml_output_attributes PASSED")

def test_validate_xml_output_with_stray_tags():
    response = "</thinking><thinking>foo</thinking>"
    # This should PASS because there is a valid pair later in the string.
    # The first </thinking> is treated as noise.
    assert validate_xml_output(response, ["thinking"]) is True
    print("test_validate_xml_output_with_stray_tags PASSED")

def test_validate_xml_output_missing_closing():
    response = "<thinking>foo"
    assert validate_xml_output(response, ["thinking"]) is False
    print("test_validate_xml_output_missing_closing PASSED")

def run_tests():
    test_validate_xml_output_valid()
    test_validate_xml_output_markdown_block()
    test_validate_xml_output_case_mismatch()
    test_validate_xml_output_mixed_case()
    test_validate_xml_output_attributes()
    test_validate_xml_output_with_stray_tags()
    test_validate_xml_output_missing_closing()
    print("ALL TESTS PASSED")

if __name__ == "__main__":
    run_tests()
