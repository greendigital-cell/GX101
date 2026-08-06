"""
Test script to verify clause extraction is working
"""
import PyPDF2
import io
import json
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF"""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        pages_text = {}
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            pages_text[page_num + 1] = text
    return pages_text

def test_extraction(pages_text, start_page, end_page):
    """Test extraction for a specific page range"""
    
    # Combine text from pages
    chunk_text = ""
    for page_num in range(start_page, end_page + 1):
        if page_num in pages_text:
            chunk_text += f"\n--- Page {page_num} ---\n{pages_text[page_num]}"
    
    prompt = f"""Analyze the following Business Requirements Document (BRD) text from pages {start_page}-{end_page} and extract ALL requirement clauses.

**IMPORTANT:** Requirements can appear in various formats:
1. **Narrative format**: "The system shall..." statements embedded in paragraphs
2. **Tabular format**: Requirements in tables with IDs like FR-01, FR-02, NFR-01, etc.
3. **Numbered lists**: Requirements as numbered or bulleted items
4. **Mixed format**: Any combination of the above

**What to extract:**
- Functional Requirements (FR-XX, F.X, etc.)
- Non-Functional Requirements (NFR-XX, NF.X, etc.)
- Business Rules
- Data Requirements and validations
- Any statement describing system behavior, constraints, or expectations
- Requirements with 100+ words of meaningful content

**Instructions:**
For each requirement you find:
1. **clause_id**: Use the existing ID from the document (e.g., "FR-01", "NFR-03") if available. If no ID exists, create one in format "BRD-P{start_page}-R{{number}}" (e.g., "BRD-P4-R1")
2. **text**: Extract the COMPLETE requirement text including all details, descriptions, and context. Combine ID, title, and description if they're separate.
3. **page**: Identify the page number where it appears (between {start_page} and {end_page})

**Output Format:**
Return ONLY a JSON array in this exact format:
[
  {{
    "clause_id": "FR-01",
    "text": "Add Employee: The system shall allow an authorized HR user to create a new employee record by entering personal, contact, job, and statutory details.",
    "page": 4
  }},
  {{
    "clause_id": "FR-02",
    "text": "Mandatory Field Validation: The system shall enforce all mandatory fields before allowing submission.",
    "page": 4
  }}
]

If no requirements are found, return an empty array: []

**BRD Text to analyze:**
{chunk_text}

**Remember:** 
- Extract ALL requirements, even if in table format
- Be inclusive - when in doubt, extract it
- Return ONLY the JSON array, no explanation or markdown formatting"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a requirements analyst expert at extracting ALL requirement clauses from BRD documents regardless of format (narrative, tabular, or mixed). You extract requirements from tables, lists, and prose. Be inclusive and comprehensive. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Try to parse JSON
        try:
            clauses = json.loads(content)
            return clauses
        except json.JSONDecodeError:
            # Try to extract from code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                clauses = json.loads(json_match.group(1))
                return clauses
            else:
                print("Failed to parse JSON:")
                print(content)
                return []
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    print("Testing clause extraction...")
    
    # Extract PDF text
    pdf_path = "BRD_HRM_Employee_Registration.pdf"
    pages_text = extract_text_from_pdf(pdf_path)
    
    print(f"Total pages: {len(pages_text)}")
    
    # Test on pages 4-5 where requirements are located
    print("\nTesting extraction on pages 4-5 (where FR requirements are)...")
    clauses = test_extraction(pages_text, 4, 5)
    
    print(f"\nExtracted {len(clauses)} clauses:")
    for clause in clauses:
        print(f"\n- {clause['clause_id']} (Page {clause['page']})")
        print(f"  Text: {clause['text'][:100]}...")
    
    # Test on all pages
    print("\n\nTesting extraction on all pages (1-10)...")
    all_clauses = test_extraction(pages_text, 1, 10)
    print(f"\nExtracted {len(all_clauses)} total clauses")
    
    if len(all_clauses) > 0:
        print("\n✓ SUCCESS: Clauses are being extracted!")
    else:
        print("\n✗ FAILURE: No clauses extracted")
