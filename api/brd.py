from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Query, BackgroundTasks, Depends
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, HttpUrl
from pathlib import Path
import subprocess
from typing import List, Optional, Any, Dict
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import certifi
import io
import tempfile
import json
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from pymongo import MongoClient
from openai import OpenAI
import httpx
import httpx
import PyPDF2
import re
import jwt
import asyncio

load_dotenv()

# MongoDB
MONGODB_URL = "mongodb+srv://zainisrar_db_user:zain123@cluster0.myxypuf.mongodb.net/gx1"
if not MONGODB_URL:
    raise ValueError("MONGODB_URL environment variable is not set")
async_client = AsyncIOMotorClient(MONGODB_URL, tlsCAFile=certifi.where()) if MONGODB_URL.startswith("mongodb+srv") else AsyncIOMotorClient(MONGODB_URL)
db = async_client.gx1
nlp_collection = db.userdata
brd_collection = db.brd_documents
clauses_collection = db.clauses



SECRET_KEY = "testing it"
ALGORITHM = "HS256"

router = APIRouter()
security = HTTPBearer()

# Configure OpenAI client with custom timeout and retry settings
http_client = httpx.Client(
    timeout=httpx.Timeout(60.0, connect=10.0),  # 60s total, 10s connect
    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
)

clients = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "").strip(),  # Strip whitespace and newlines
    http_client=http_client,
    max_retries=3
)

# Verify OpenAI API connectivity on startup
def verify_openai_connection():
    """Test OpenAI API connectivity"""
    try:
        test_response = clients.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5,
            timeout=10.0
        )
        print("✓ OpenAI API connection verified successfully")
        return True
    except Exception as e:
        print(f"✗ OpenAI API connection failed: {type(e).__name__} - {str(e)}")
        print(f"  This may be due to:")
        print(f"  - Container network restrictions")
        print(f"  - Firewall blocking api.openai.com")
        print(f"  - Invalid or expired API key")
        print(f"  - No internet access from container")
        print(f"\n  Run 'python test_network.py' for detailed diagnostics")
        return False

# Test connection on module load (will log result but not block startup)
try:
    verify_openai_connection()
except:
    pass

cloudinary.config(
    cloud_name="dtkxm4abz",
    api_key="135213472543525",
    api_secret="7_RY2sgYVwKu04BAw1goYJn7aYY"
)


# Authentication Helper Functions
def verify_token(token: str) -> str:
    """Verify JWT token and return email"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=401,
                detail="Could not validate credentials"
            )
        return email
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    email = verify_token(credentials.credentials)
    user = await async_client.gx1.users.find_one({"email": email})
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )
    return user


# Pydantic Models
class Clause(BaseModel):
    clause_id: str
    text: str
    page: int
    status: str = "Unprocessed"

class BRDDocument(BaseModel):
    document_id: str
    filename: str
    total_pages: int
    clauses: List[Clause]
    created_at: datetime
    processed_at: Optional[datetime] = None


# Helper Functions
def extract_text_from_pdf(pdf_file: io.BytesIO) -> Dict[int, str]:
    """
    Extract text from PDF file page by page
    
    Args:
        pdf_file: BytesIO object containing PDF data
        
    Returns:
        Dictionary with page number as key and extracted text as value
    """
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    pages_text = {}
    
    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]
        text = page.extract_text()
        pages_text[page_num + 1] = text  # 1-indexed page numbers
    
    return pages_text


def chunk_pages(pages_text: Dict[int, str], chunk_size: int = 10) -> List[Dict]:
    """
    Chunk pages into groups
    
    Args:
        pages_text: Dictionary of page number to text
        chunk_size: Number of pages per chunk
        
    Returns:
        List of chunks with page ranges and combined text
    """
    chunks = []
    total_pages = len(pages_text)
    
    for start_page in range(1, total_pages + 1, chunk_size):
        end_page = min(start_page + chunk_size - 1, total_pages)
        
        # Combine text from pages in this chunk
        chunk_text = ""
        for page_num in range(start_page, end_page + 1):
            if page_num in pages_text:
                chunk_text += f"\n--- Page {page_num} ---\n{pages_text[page_num]}"
        
        chunks.append({
            "chunk_number": len(chunks) + 1,
            "start_page": start_page,
            "end_page": end_page,
            "text": chunk_text
        })
    
    return chunks


async def extract_clauses_with_llm(chunk_text: str, start_page: int, end_page: int, chunk_number: int) -> List[Dict]:
    """
    Use LLM to extract clauses from text chunk
    
    Args:
        chunk_text: Text content to analyze
        start_page: Starting page number of chunk
        end_page: Ending page number of chunk
        chunk_number: Chunk identifier
        
    Returns:
        List of extracted clauses with metadata
    """
    
    # Check chunk size - warn if too large
    chunk_length = len(chunk_text)
    if chunk_length > 15000:
        print(f"Warning: Chunk {chunk_number} is large ({chunk_length} chars). This may cause timeouts.")
    
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
        # Retry logic for connection errors
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                response = clients.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a requirements analyst expert at extracting ALL requirement clauses from BRD documents regardless of format (narrative, tabular, or mixed). You extract requirements from tables, lists, and prose. Be inclusive and comprehensive. Always respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4000,
                    timeout=60.0  # 60 second timeout per request
                )
                
                # If successful, break out of retry loop
                break
                
            except Exception as conn_error:
                if attempt < max_retries - 1:
                    print(f"Connection attempt {attempt + 1} failed: {str(conn_error)}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    raise conn_error
        
        content = response.choices[0].message.content.strip()
        
        # Try to parse the JSON response
        try:
            clauses = json.loads(content)
            
            # Add status field to each clause
            for clause in clauses:
                clause["status"] = "Unprocessed"
            
            return clauses
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', content, re.DOTALL)
            if json_match:
                clauses = json.loads(json_match.group(1))
                for clause in clauses:
                    clause["status"] = "Unprocessed"
                return clauses
            else:
                print(f"Failed to parse LLM response as JSON: {content}")
                return []
                
    except Exception as e:
        error_type = type(e).__name__
        print(f"Error calling LLM ({error_type}): {str(e)}")
        import traceback
        traceback.print_exc()
        return []








@router.post("/extract-clauses-from-pdf")
async def extract_clauses_from_pdf(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    brd_title: str = Form(...),
    short_description: str = Form(...),
    business_domain: str = Form(...),
    sub_domain: str = Form(...),
    complexity: str = Form(...),
    project_type: str = Form(...),
    regulatory_impact: str = Form(...),
    assign_to: str = Form(...),
    reviewers: str = Form(...),
    priority: str = Form(...),
    target_release_date: str = Form(...),
    gsolve_project: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    chunk_size: int = Query(default=10, description="Number of pages per chunk")
):
    """
    Upload a PDF file with BRD metadata, extract text in chunks, and use LLM to extract requirement clauses
    
    Args:
        file: PDF file to process
        user_id: User ID
        brd_title: Title of the BRD document
        short_description: Short description of the BRD
        business_domain: Business domain
        sub_domain: Sub domain
        complexity: Project complexity
        project_type: Type of project
        regulatory_impact: Regulatory impact level
        assign_to: Person assigned to
        reviewers: Comma-separated list of reviewers
        priority: Priority level
        target_release_date: Target release date
        gsolve_project: Optional JSON string containing GreenSolve project data
        tags: Optional comma-separated list of tags
        notes: Optional notes
        chunk_size: Number of pages to process per chunk (default: 10)
        
    Returns:
        Document ID and extracted clauses stored in MongoDB
    """
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        # Parse reviewers and tags
        reviewers_list = [r.strip() for r in reviewers.split(",")] if reviewers else []
        tags_list = [t.strip() for t in tags.split(",")] if tags else []
        
        # Parse gsolve_project JSON if provided
        gsolve_project_data = None
        project_id = None
        if gsolve_project:
            try:
                gsolve_project_data = json.loads(gsolve_project)
                if isinstance(gsolve_project_data, dict):
                    project_id = str(gsolve_project_data.get("id", ""))
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON format for gsolve_project")
        
        # Check if project already has a BRD
        if project_id:
            existing_brd = await brd_collection.find_one({"project_id": project_id})
            if existing_brd:
                raise HTTPException(
                    status_code=409,  # Conflict
                    detail=f"Project already has a BRD. Project ID: {project_id}. BRD ID: {str(existing_brd['_id'])}. Please use a different project or delete the existing BRD first."
                )
        
        # Read PDF file
        pdf_content = await file.read()
        pdf_file = io.BytesIO(pdf_content)
        
        # Extract text from all pages
        print(f"Extracting text from PDF: {file.filename} for user: {user_id}")
        pages_text = extract_text_from_pdf(pdf_file)
        total_pages = len(pages_text)
        
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDF appears to be empty or unreadable")
        
        # Create chunks
        print(f"Creating chunks with {chunk_size} pages per chunk")
        chunks = chunk_pages(pages_text, chunk_size)
        
        # Process each chunk with LLM
        all_clauses = []
        for chunk in chunks:
            print(f"Processing chunk {chunk['chunk_number']}: Pages {chunk['start_page']}-{chunk['end_page']}")
            
            clauses = await extract_clauses_with_llm(
                chunk['text'],
                chunk['start_page'],
                chunk['end_page'],
                chunk['chunk_number']
            )
            
            all_clauses.extend(clauses)
            print(f"Extracted {len(clauses)} clauses from chunk {chunk['chunk_number']}")
        
        # Create document record
        document_id = str(ObjectId())
        
        # Extract project_id from gsolve_project if available
        project_id = None
        if gsolve_project_data and isinstance(gsolve_project_data, dict):
            project_id = str(gsolve_project_data.get("id", ""))
        
        document_data = {
            "_id": ObjectId(document_id),
            "user_id": user_id,
            
            # BRD Metadata
            "brd_title": brd_title,
            "short_description": short_description,
            "filename": file.filename,
            
            # Classification
            "business_domain": business_domain,
            "sub_domain": sub_domain,
            "complexity": complexity,
            "project_type": project_type,
            "regulatory_impact": regulatory_impact,
            
            # Assignment
            "assign_to": assign_to,
            "reviewers": reviewers_list,
            
            # Priority & Target
            "priority": priority,
            "target_release_date": target_release_date,
            
            # GreenSolve Project Data
            "gsolve_project": gsolve_project_data,
            "project_id": project_id,
            
            # Tags & Notes
            "tags": tags_list,
            "notes": notes,
            
            # Document Processing Info
            "total_pages": total_pages,
            "total_clauses": len(all_clauses),
            "status": "Submitted",
            "created_at": datetime.utcnow(),
            "processed_at": datetime.utcnow(),
            "chunk_size": chunk_size,
            "total_chunks": len(chunks)
        }
        
        # Store BRD document in MongoDB
        await brd_collection.insert_one(document_data)
        
        # Store each clause individually in clauses collection
        clause_documents = []
        for clause in all_clauses:
            clause_doc = {
                "_id": ObjectId(),
                "user_id": user_id,
                "project_id": project_id,
                "brd_id": document_id,
                "brd_title": brd_title,
                "clause_id": clause.get("clause_id"),
                "text": clause.get("text"),
                "page": clause.get("page"),
                "status": clause.get("status", "Unprocessed"),
                "created_at": datetime.utcnow()
            }
            clause_documents.append(clause_doc)
        
        # Bulk insert clauses if any exist
        if clause_documents:
            await clauses_collection.insert_many(clause_documents)
            print(f"Stored {len(clause_documents)} clauses in clauses collection")
        
        print(f"Document stored with ID: {document_id} for user: {user_id}")
        print(f"Total clauses extracted: {len(all_clauses)}")
        
        return {
            "success": True,
            "document_id": document_id,
            "user_id": user_id,
            "brd_title": brd_title,
            "filename": file.filename,
            "total_pages": total_pages,
            "total_chunks": len(chunks),
            "total_clauses": len(all_clauses),
            "clauses": all_clauses,
            "message": f"Successfully processed {total_pages} pages and extracted {len(all_clauses)} clauses"
        }
        
    except PyPDF2.errors.PdfReadError as e:
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@router.post("/extract-clauses-from-pdf-stream")
async def extract_clauses_from_pdf_stream(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    brd_title: str = Form(...),
    short_description: str = Form(...),
    business_domain: str = Form(...),
    sub_domain: str = Form(...),
    complexity: str = Form(...),
    project_type: str = Form(...),
    regulatory_impact: str = Form(...),
    assign_to: str = Form(...),
    reviewers: str = Form(...),
    priority: str = Form(...),
    target_release_date: str = Form(...),
    gsolve_project: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    chunk_size: int = Query(default=10, description="Number of pages per chunk")
):
    """
    Upload a PDF file with streaming progress updates
    Returns Server-Sent Events (SSE) with real-time progress
    """
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    async def generate_progress():
        try:
            # Send initial status
            yield f"data: {json.dumps({'status': 'started', 'message': 'Processing started'})}\n\n"
            
            # Parse gsolve_project JSON to get project_id
            gsolve_project_data = None
            project_id = None
            if gsolve_project:
                try:
                    gsolve_project_data = json.loads(gsolve_project)
                    if isinstance(gsolve_project_data, dict):
                        project_id = str(gsolve_project_data.get("id", ""))
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid JSON format for gsolve_project'})}\n\n"
                    return
            
            # Check if project already has a BRD
            if project_id:
                existing_brd = await brd_collection.find_one({"project_id": project_id})
                if existing_brd:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Project already has a BRD. Project ID: {project_id}. Please use a different project or delete the existing BRD first.', 'error_code': 'BRD_ALREADY_EXISTS'})}\n\n"
                    return
            
            # Parse reviewers and tags
            reviewers_list = [r.strip() for r in reviewers.split(",")] if reviewers else []
            tags_list = [t.strip() for t in tags.split(",")] if tags else []
            
            # Read PDF file
            pdf_content = await file.read()
            pdf_file = io.BytesIO(pdf_content)
            
            yield f"data: {json.dumps({'status': 'reading', 'message': 'Reading PDF file'})}\n\n"
            
            # Extract text from all pages
            pages_text = extract_text_from_pdf(pdf_file)
            total_pages = len(pages_text)
            
            if total_pages == 0:
                yield f"data: {json.dumps({'status': 'error', 'message': 'PDF appears to be empty or unreadable'})}\n\n"
                return
            
            yield f"data: {json.dumps({'status': 'extracted', 'total_pages': total_pages, 'message': f'Extracted text from {total_pages} pages'})}\n\n"
            
            # Create chunks
            chunks = chunk_pages(pages_text, chunk_size)
            total_chunks = len(chunks)
            
            yield f"data: {json.dumps({'status': 'chunked', 'total_chunks': total_chunks, 'message': f'Created {total_chunks} chunks'})}\n\n"
            
            # Process each chunk with LLM
            all_clauses = []
            for chunk in chunks:
                chunk_num = chunk['chunk_number']
                start_page = chunk['start_page']
                end_page = chunk['end_page']
                
                yield f"data: {json.dumps({'status': 'processing_chunk', 'chunk': chunk_num, 'total_chunks': total_chunks, 'start_page': start_page, 'end_page': end_page, 'message': f'Processing chunk {chunk_num}/{total_chunks} (pages {start_page}-{end_page})'})}\n\n"
                
                clauses = await extract_clauses_with_llm(
                    chunk['text'],
                    start_page,
                    end_page,
                    chunk_num
                )
                
                all_clauses.extend(clauses)
                
                yield f"data: {json.dumps({'status': 'chunk_completed', 'chunk': chunk_num, 'total_chunks': total_chunks, 'clauses_extracted': len(clauses), 'total_clauses_so_far': len(all_clauses), 'message': f'Extracted {len(clauses)} clauses from chunk {chunk_num}'})}\n\n"
            
            yield f"data: {json.dumps({'status': 'extraction_complete', 'total_clauses': len(all_clauses), 'message': f'Completed extraction: {len(all_clauses)} clauses found'})}\n\n"
            
            # Create document record
            document_id = str(ObjectId())
            
            document_data = {
                "_id": ObjectId(document_id),
                "user_id": user_id,
                "brd_title": brd_title,
                "short_description": short_description,
                "filename": file.filename,
                "business_domain": business_domain,
                "sub_domain": sub_domain,
                "complexity": complexity,
                "project_type": project_type,
                "regulatory_impact": regulatory_impact,
                "assign_to": assign_to,
                "reviewers": reviewers_list,
                "priority": priority,
                "target_release_date": target_release_date,
                "gsolve_project": gsolve_project_data,
                "project_id": project_id,
                "tags": tags_list,
                "notes": notes,
                "total_pages": total_pages,
                "total_clauses": len(all_clauses),
                "status": "Submitted",
                "created_at": datetime.utcnow(),
                "processed_at": datetime.utcnow(),
                "chunk_size": chunk_size,
                "total_chunks": len(chunks)
            }
            
            yield f"data: {json.dumps({'status': 'saving', 'message': 'Saving to database'})}\n\n"
            
            # Store BRD document in MongoDB
            await brd_collection.insert_one(document_data)
            
            # Store each clause individually in clauses collection
            clause_documents = []
            for idx, clause in enumerate(all_clauses, 1):
                clause_doc = {
                    "_id": ObjectId(),
                    "user_id": user_id,
                    "project_id": project_id,
                    "brd_id": document_id,
                    "brd_title": brd_title,
                    "clause_id": clause.get("clause_id"),
                    "text": clause.get("text"),
                    "page": clause.get("page"),
                    "status": clause.get("status", "Unprocessed"),
                    "created_at": datetime.utcnow()
                }
                clause_documents.append(clause_doc)
                
                # Send progress every 5 clauses
                if idx % 5 == 0 or idx == len(all_clauses):
                    yield f"data: {json.dumps({'status': 'saving_clauses', 'saved': idx, 'total': len(all_clauses), 'message': f'Saving clauses {idx}/{len(all_clauses)}'})}\n\n"
            
            # Bulk insert clauses if any exist
            if clause_documents:
                await clauses_collection.insert_many(clause_documents)
            
            # Send final success message
            yield f"data: {json.dumps({'status': 'completed', 'document_id': document_id, 'user_id': user_id, 'brd_title': brd_title, 'total_pages': total_pages, 'total_clauses': len(all_clauses), 'message': 'Processing completed successfully'})}\n\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/brd-documents/{user_id}")
async def get_brd_documents(user_id: str):
    """
    Get all BRD documents for a specific user
    
    Args:
        user_id: User ID to filter documents
        
    Returns:
        List of all BRD documents belonging to the user
    """
    try:
        documents = []
        async for doc in brd_collection.find({"user_id": user_id}).sort("created_at", -1):
            doc["_id"] = str(doc["_id"])
            documents.append(doc)
        
        return {
            "success": True,
            "count": len(documents),
            "user_id": user_id,
            "documents": documents
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {str(e)}")


@router.get("/brd-document/{document_id}")
async def get_brd_document(document_id: str):
    """
    Get a specific BRD document by ID
    
    Args:
        document_id: MongoDB document ID
        
    Returns:
        Document with all its clauses
    """
    try:
        document = await brd_collection.find_one({"_id": ObjectId(document_id)})
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document["_id"] = str(document["_id"])
        
        return {
            "success": True,
            "document": document
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching document: {str(e)}")


@router.delete("/brd-document/{document_id}")
async def delete_brd_document(document_id: str):
    """
    Delete a BRD document by ID
    
    Args:
        document_id: MongoDB document ID
        
    Returns:
        Success message
    """
    try:
        result = await brd_collection.delete_one({"_id": ObjectId(document_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "message": "Document deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")


@router.get("/clauses/user/{user_id}")
async def get_clauses_by_user(user_id: str):
    """
    Get all clauses for a specific user
    
    Args:
        user_id: User ID
        
    Returns:
        List of all clauses belonging to the user
    """
    try:
        clauses = []
        async for clause in clauses_collection.find({"user_id": user_id}).sort("created_at", -1):
            clause["_id"] = str(clause["_id"])
            clauses.append(clause)
        
        return {
            "success": True,
            "count": len(clauses),
            "user_id": user_id,
            "clauses": clauses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clauses: {str(e)}")


@router.get("/clauses/project/{project_id}")
async def get_clauses_by_project(project_id: str):
    """
    Get all clauses for a specific project
    
    Args:
        project_id: Project ID from GreenSolve
        
    Returns:
        List of all clauses for the project
    """
    try:
        clauses = []
        async for clause in clauses_collection.find({"project_id": project_id}).sort("created_at", -1):
            clause["_id"] = str(clause["_id"])
            clauses.append(clause)
        
        return {
            "success": True,
            "count": len(clauses),
            "project_id": project_id,
            "clauses": clauses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clauses: {str(e)}")


@router.get("/clauses/brd/{brd_id}")
async def get_clauses_by_brd(brd_id: str):
    """
    Get all clauses for a specific BRD document
    
    Args:
        brd_id: BRD Document ID
        
    Returns:
        List of all clauses for the BRD document
    """
    try:
        clauses = []
        async for clause in clauses_collection.find({"brd_id": brd_id}).sort("page", 1):
            clause["_id"] = str(clause["_id"])
            clauses.append(clause)
        
        return {
            "success": True,
            "count": len(clauses),
            "brd_id": brd_id,
            "clauses": clauses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clauses: {str(e)}")


@router.get("/clauses/user/{user_id}/project/{project_id}")
async def get_clauses_by_user_and_project(user_id: str, project_id: str):
    """
    Get all clauses for a specific user and project
    
    Args:
        user_id: User ID
        project_id: Project ID from GreenSolve
        
    Returns:
        List of all clauses for the user and project
    """
    try:
        clauses = []
        async for clause in clauses_collection.find({
            "user_id": user_id,
            "project_id": project_id
        }).sort("created_at", -1):
            clause["_id"] = str(clause["_id"])
            clauses.append(clause)
        
        return {
            "success": True,
            "count": len(clauses),
            "user_id": user_id,
            "project_id": project_id,
            "clauses": clauses
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clauses: {str(e)}")


@router.put("/clause/{clause_id}/status")
async def update_clause_status(
    clause_id: str,
    status: str = Query(..., description="New status for the clause")
):
    """
    Update the status of a specific clause
    
    Args:
        clause_id: Clause MongoDB ID
        status: New status value
        
    Returns:
        Success message with updated clause
    """
    try:
        result = await clauses_collection.update_one(
            {"_id": ObjectId(clause_id)},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Clause not found")
        
        updated_clause = await clauses_collection.find_one({"_id": ObjectId(clause_id)})
        updated_clause["_id"] = str(updated_clause["_id"])
        
        return {
            "success": True,
            "message": "Clause status updated successfully",
            "clause": updated_clause
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating clause: {str(e)}")


@router.put("/brd-document/{document_id}/status")
async def update_brd_status(
    document_id: str,
    status: str = Query(..., description="New status for the BRD document")
):
    """
    Update the status of a BRD document
    
    Args:
        document_id: BRD Document MongoDB ID
        status: New status value (e.g., Submitted, In Review, Approved, Rejected)
        
    Returns:
        Success message with updated document
    """
    try:
        result = await brd_collection.update_one(
            {"_id": ObjectId(document_id)},
            {"$set": {"status": status, "status_updated_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="BRD document not found")
        
        updated_doc = await brd_collection.find_one({"_id": ObjectId(document_id)})
        updated_doc["_id"] = str(updated_doc["_id"])
        
        return {
            "success": True,
            "message": "BRD document status updated successfully",
            "document": updated_doc
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating BRD status: {str(e)}")


@router.get("/gsolve/project-list")
async def get_project_list():
    """
    Fetch project list from GreenSolve API
    
    Returns:
        JSON data from the GreenSolve API with timestamp and status
    """
    try:
        url = "https://app-gsolve.green.com.pg/project_list/digitall/"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            return {
                "data": response.json(),
                "timestamp": datetime.now(),
                "status_code": response.status_code,
                "message": "Project list fetched successfully"
            }
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"HTTP error occurred: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Request error occurred: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
