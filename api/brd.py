from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Query, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
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

load_dotenv()

# MongoDB
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://zainisrar2007_db_user:SUcRZUeK6sRJA3KL@cluster0.earf4sd.mongodb.net/")
async_client = AsyncIOMotorClient(MONGODB_URL, tlsCAFile=certifi.where()) if MONGODB_URL.startswith("mongodb+srv") else AsyncIOMotorClient(MONGODB_URL)
db = async_client.gx1
nlp_collection = db.userdata

sync_client = MongoClient(MONGODB_URL, tlsCAFile=certifi.where()) if MONGODB_URL.startswith("mongodb+srv") else MongoClient(MONGODB_URL)
sync_db = sync_client.fastapi_db
projects_collection = sync_db.projects
users_collection = sync_db.users

SECRET_KEY = "testing it"
ALGORITHM = "HS256"

router = APIRouter()

clients = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

cloudinary.config(
    cloud_name="dtkxm4abz",
    api_key="135213472543525",
    api_secret="7_RY2sgYVwKu04BAw1goYJn7aYY"
)

# ------------------------------
# Models
# ------------------------------
class PromptRequest(BaseModel):
    prompt: str

class BRDRequest(BaseModel):
    title: str
    description: str

# ------------------------------
# LLM Handler
# ------------------------------
def send_to_llm(prompt: str) -> List[str]:
    system_prompt = f"""
You are an expert solar system assistant.

A user has described their solar system requirement in natural language. Your job is to:
- Analyze the prompt
- Identify missing or unclear information required to perform load analysis and system sizing (PV, Inverter, Battery)
- Return only **4 to 5 smart, merged questions** that efficiently gather all essential technical details

Each question should combine related data points where possible, to minimize user effort while maximizing information collected.

User Prompt:
\"\"\"
{prompt}
\"\"\"

Output:
A numbered list of 4–5 optimized questions to collect required details for solar system sizing.
"""
    response = clients.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": system_prompt}]
    )
    raw_text = response.choices[0].message.content.strip()
    questions = []
    for line in raw_text.splitlines():
        if line.strip():
            parts = line.strip().split(".", 1)
            if len(parts) == 2 and parts[0].isdigit():
                questions.append(parts[1].strip())
    return questions




@router.get("/html/{filename}")
async def get_html_file(filename: str):
    """
    Serve generated HTML file
    """
    try:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_ui")
        file_path = os.path.join(output_dir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="HTML file not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return HTMLResponse(content=content)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading HTML file: {str(e)}")




@router.post("/BRD")
async def brd(
    background_tasks: BackgroundTasks,
    title: str = Form(None),
    description: str = Form(None),
    brd_file: UploadFile = File(None),
    # Project Selection (From GSolve)
    project_code: str = Form(None),
    project_name: str = Form(None),
    client: str = Form(None),
    project_manager: str = Form(None),
    status: str = Form(None),
    # Project Metadata (Read-only from GSolve)
    start_date: str = Form(None),
    target_end_date: str = Form(None),
    currency: str = Form(None),
    project_type: str = Form(None),
    business_domain: str = Form(None),
    sub_domain: str = Form(None),
    contract_reference: str = Form(None),
    budget: str = Form(None),
    project_priority: str = Form(None),
    project_stage: str = Form(None),
    last_updated: str = Form(None),
    updated_by: str = Form(None),
    # Priority & Target (Section 6)
    priority: str = Form(None),
    target_release_date: str = Form(None),
    # Classification
    complexity: str = Form(None),
    regulatory_impact: str = Form(None),
    # Assignment
    assign_to: str = Form(None),
    reviewers: str = Form(None),  # Comma-separated string
    # Tags & Notes
    tags: str = Form(None),  # Comma-separated string
    notes: str = Form(None)
):
    """
    Accept BRD input via title+description OR uploaded document.
    Processes BRD generation in background and returns immediately.
    User can check status using the returned data_id.
    """
    try:
        # Step 1: Get BRD content
        brd_content = ""
        
        if brd_file:
            # Read uploaded document
            file_content = await brd_file.read()
            
            # Handle different file types
            if brd_file.filename.endswith('.txt'):
                brd_content = file_content.decode('utf-8')
            elif brd_file.filename.endswith('.docx'):
                try:
                    import docx
                    doc_file = io.BytesIO(file_content)
                    doc = docx.Document(doc_file)
                    brd_content = "\n".join([para.text for para in doc.paragraphs])
                except ImportError:
                    raise HTTPException(status_code=400, detail="DOCX support requires python-docx library")
            elif brd_file.filename.endswith('.pdf'):
                try:
                    import PyPDF2
                    pdf_file = io.BytesIO(file_content)
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    brd_content = ""
                    for page in pdf_reader.pages:
                        brd_content += page.extract_text() + "\n"
                except ImportError:
                    raise HTTPException(status_code=400, detail="PDF support requires PyPDF2 library. Install: pip install PyPDF2")
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")
            else:
                brd_content = file_content.decode('utf-8', errors='ignore')
            
            brd_title = brd_file.filename.replace('.txt', '').replace('.docx', '').replace('.pdf', '')
        else:
            # Use form data
            if not title or not description:
                raise HTTPException(status_code=400, detail="Either provide title+description or upload a BRD file")
            
            brd_title = title
            brd_content = description
        
        # Step 2: Store BRD in MongoDB immediately with "pending" status
        reviewers_list = [r.strip() for r in reviewers.split(',')] if reviewers else []
        tags_list = [t.strip() for t in tags.split(',')] if tags else []
        
        brd_record = {
            # BRD Document Info
            "title": brd_title,
            "content": brd_content,
            "html_file": None,  # Will be updated by background task
            "html_filename": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "design_system": "GX1",
            "processing_status": "pending",  # Track processing status
            
            # Project Selection (From GSolve)
            "project_code": project_code,
            "project_name": project_name,
            "client": client,
            "project_manager": project_manager,
            "status": status,
            
            # Project Metadata (Read-only from GSolve)
            "start_date": start_date,
            "target_end_date": target_end_date,
            "currency": currency,
            "project_type": project_type,
            "business_domain": business_domain,
            "sub_domain": sub_domain,
            "contract_reference": contract_reference,
            "budget": budget,
            "project_priority": project_priority,
            "project_stage": project_stage,
            "last_updated": last_updated,
            "updated_by": updated_by,
            
            # Priority & Target
            "priority": priority or project_priority,
            "target_release_date": target_release_date or target_end_date,
            
            # Classification
            "complexity": complexity,
            "regulatory_impact": regulatory_impact,
            
            # Assignment
            "assign_to": assign_to,
            "reviewers": reviewers_list,
            
            # Tags & Notes
            "tags": tags_list,
            "notes": notes
        }
        
        result = await nlp_collection.insert_one(brd_record)
        brd_id = str(result.inserted_id)
        
        # Step 3: Add background task to process BRD
        gx1_design_path = os.path.join(os.path.dirname(__file__), "gx1.json")
        background_tasks.add_task(
            process_brd_background,
            brd_id,
            brd_title,
            brd_content,
            gx1_design_path
        )
        
        # Step 4: Return immediately
        return {
            "message": "BRD submitted successfully. Processing in background.",
            "data_id": brd_id,
            "processing_status": "pending",
            "status_check_url": f"/api/project-sites/BRD/{brd_id}",
            "project_code": project_code,
            "project_name": project_name,
            "note": "Use the data_id to check processing status via GET /api/project-sites/BRD/{data_id}"
        }
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error submitting BRD: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error submitting BRD: {str(e)}")


@router.get("/BRD/{brd_id}")
async def get_brd_by_id(brd_id: str):
    """
    Get BRD data by ID from userdata collection.
    This returns the BRD document with all project details and generated UI information.
    
    Example: GET /api/project-sites/BRD/6a70c844f7bc4b4a7c24c166
    """
    try:
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(brd_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid BRD ID format")
        
        # Fetch BRD from userdata collection
        brd_data = await nlp_collection.find_one({"_id": obj_id})
        
        if not brd_data:
            raise HTTPException(status_code=404, detail="BRD not found")
        
        # Convert ObjectId to string
        brd_data["id"] = str(brd_data.pop("_id"))
        
        return {
            "message": "BRD fetched successfully",
            "data": brd_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching BRD: {str(e)}")


@router.get("/BRD/list/all")
async def get_all_brds(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return")
):
    """
    Get all BRD records from userdata collection with pagination.
    
    Example: GET /api/project-sites/BRD/list/all?skip=0&limit=10
    """
    try:
        # Count total documents
        total = await nlp_collection.count_documents({})
        
        # Fetch documents with pagination
        cursor = nlp_collection.find({}).skip(skip).limit(limit).sort("created_at", -1)
        brds = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for brd in brds:
            brd["id"] = str(brd.pop("_id"))
        
        return {
            "message": "BRDs fetched successfully",
            "total": total,
            "skip": skip,
            "limit": limit,
            "data": brds
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching BRDs: {str(e)}")


@router.get("/BRD/by-project/{project_code}")
async def get_brds_by_project_code(
    project_code: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return")
):
    """
    Get all BRD records for a specific project code from userdata collection.
    
    Example: GET /api/project-sites/BRD/by-project/GSolve?skip=0&limit=10
    """
    try:
        # Query for this project
        query = {"project_code": project_code}
        
        # Count total documents for this project
        total = await nlp_collection.count_documents(query)
        
        if total == 0:
            return {
                "message": f"No BRDs found for project code {project_code}",
                "total": 0,
                "skip": skip,
                "limit": limit,
                "data": []
            }
        
        # Fetch documents with pagination
        cursor = nlp_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        brds = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for brd in brds:
            brd["id"] = str(brd.pop("_id"))
        
        return {
            "message": "BRDs fetched successfully",
            "total": total,
            "skip": skip,
            "limit": limit,
            "project_code": project_code,
            "data": brds
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching BRDs: {str(e)}")


def generate_ui_from_brd(title: str, brd_content: str, gx1_design: dict) -> str:
    """
    Use OpenAI to analyze BRD and generate HTML UI based on GX1 design system
    """
    
    system_prompt = f"""
You are an expert UI designer specializing in the GX1 Design System.

**GX1 Design System Rules:**
{json.dumps(gx1_design, indent=2)}

**Your Task:**
Analyze the following Business Requirements Document (BRD) and generate a complete HTML page that:
1. Implements the described functionality
2. Strictly follows ALL GX1 design system rules (colors, typography, layout, form fields, icons)
3. Uses semantic HTML5 with proper structure
4. Includes inline CSS following GX1 tokens
5. Has 75-85% content occupancy (dense, not empty)
6. Uses Montserrat font (with Arial fallback)
7. Implements proper form fields (label above, underline border, focus states)
8. Uses brand_green (#23B14D) for active/selected states
9. Uses action_green (#0F7A35) for primary buttons
10. Never uses raw hex colors - always references design tokens in comments
11. Add placeholder text and default values in all form fields
12. For dropdowns, include realistic options with first option selected by default
13. For any data tables or lists, include 3-5 sample rows with realistic data

**CRITICAL LAYOUT REQUIREMENTS:**
- Logo must be FIXED at top-right corner using: position: fixed; top: 20px; right: 60px; max-width: 180px; z-index: 1000;
- Logo must stay visible when scrolling
- Main container padding: 20px 60px 40px 60px
- Form fields must use 2-column grid on desktop with proper gap: grid-template-columns: 1fr 1fr; gap: 20px 30px;
- Each field group spacing: margin-bottom: 20px
- NO extra gaps or margins between fields
- Section spacing: 30px between major sections
- Card padding: 30px
- Responsive: single column on mobile (max-width: 768px)

**BRD Title:** {title}

**BRD Content:**
{brd_content}

**Output Requirements:**
- Complete HTML document with <!DOCTYPE html>
- Inline CSS in <style> tag
- Responsive layout (2-column desktop grid, 1-column mobile)
- Focus on functionality described in BRD
- **MUST include logo with fixed positioning: position: fixed; top: 20px; right: 60px; max-width: 180px; z-index: 1000;**
- Logo URL: {gx1_design['logo']['url']}
- Add CSS comments referencing GX1 design tokens
- Use CSS Grid for form layouts with consistent gaps
- Professional, clean design with proper spacing

Generate ONLY the HTML code, no explanations.
"""

    try:
        response = clients.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": system_prompt}],
            temperature=0.7,
            max_tokens=4000
        )
        
        html_content = response.choices[0].message.content.strip()
        
        # Clean up markdown code blocks if present
        if html_content.startswith("```html"):
            html_content = html_content.replace("```html", "").replace("```", "").strip()
        elif html_content.startswith("```"):
            html_content = html_content.replace("```", "").strip()
        
        return html_content
    
    except Exception as e:
        # Return fallback template
        return generate_fallback_html(title, brd_content, gx1_design)


def generate_fallback_html(title: str, content: str, gx1: dict) -> str:
    """
    Generate a basic fallback HTML if AI fails
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - GX1</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Montserrat', Arial, Helvetica, sans-serif;
            font-size: 16px;
            color: {gx1['colors']['text_primary']}; /* text_primary */
            background-color: {gx1['colors']['surface_canvas']}; /* surface_canvas */
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px 60px 40px 60px;
            width: 85%; /* 75-85% content occupancy */
        }}
        
        .header {{
            position: relative;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid {gx1['colors']['brand_green']}; /* brand_green */
        }}
        
        .logo {{
            position: absolute;
            top: 0;
            right: 0;
            max-width: 180px;
            height: auto;
        }}
        
        h1 {{
            font-size: 32px;
            font-weight: 700;
            color: {gx1['colors']['text_primary']}; /* text_primary */
            margin-bottom: 20px;
        }}
        
        .content-section {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .form-field {{
            margin-bottom: 24px;
        }}
        
        .form-field label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            font-size: 14px;
            color: {gx1['colors']['text_primary']}; /* text_primary */
        }}
        
        .form-field input,
        .form-field textarea {{
            width: 100%;
            height: 40px; /* standard height */
            padding: 8px 12px;
            font-family: 'Montserrat', Arial, sans-serif;
            font-size: 14px;
            border: none;
            border-bottom: 1px solid {gx1['colors']['border_resting']}; /* border_resting */
            background: transparent;
            transition: border 0.2s;
        }}
        
        .form-field textarea {{
            height: 120px;
            resize: vertical;
        }}
        
        .form-field input:focus,
        .form-field textarea:focus {{
            outline: none;
            border-bottom: 2px solid {gx1['colors']['action_green']}; /* action_green */
            box-shadow: 0 2px 0 0 {gx1['colors']['action_green']}; /* focus ring */
        }}
        
        .btn-primary {{
            background-color: {gx1['colors']['action_green']}; /* action_green */
            color: white;
            border: none;
            padding: 12px 32px;
            font-family: 'Montserrat', Arial, sans-serif;
            font-size: 16px;
            font-weight: 600;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s;
        }}
        
        .btn-primary:hover {{
            background-color: {gx1['colors']['brand_green']}; /* brand_green */
        }}
        
        .btn-primary:focus {{
            outline: 2px solid {gx1['colors']['brand_green']}; /* focus outline */
            outline-offset: 2px;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 20px;
                width: 95%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <img src="{gx1['logo']['url']}" alt="GX1 Logo" class="logo">
        <div class="header">
            <h1>{title}</h1>
        </div>
        
        <div class="content-section">
            <h2>Requirements</h2>
            <p>{content}</p>
        </div>
        
        <div class="content-section">
            <h2>Generated Form</h2>
            <form>
                <div class="form-field">
                    <label for="name">Name</label>
                    <input type="text" id="name" name="name">
                </div>
                
                <div class="form-field">
                    <label for="email">Email</label>
                    <input type="email" id="email" name="email">
                </div>
                
                <div class="form-field">
                    <label for="notes">Additional Notes</label>
                    <textarea id="notes" name="notes"></textarea>
                </div>
                
                <button type="submit" class="btn-primary">Submit</button>
            </form>
        </div>
    </div>
</body>
</html>"""


async def process_brd_background(
    brd_id: str,
    brd_title: str,
    brd_content: str,
    gx1_design_path: str
):
    """
    Background task to process BRD and generate UI design.
    Updates the BRD record with processing status and results.
    """
    try:
        # Update status to processing
        await nlp_collection.update_one(
            {"_id": ObjectId(brd_id)},
            {"$set": {"processing_status": "processing", "updated_at": datetime.now()}}
        )
        
        # Load GX1 design system
        with open(gx1_design_path, 'r') as f:
            gx1_design = json.load(f)
        
        # Generate UI design using AI
        html_content = generate_ui_from_brd(brd_title, brd_content, gx1_design)
        
        # Save HTML file
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_ui")
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{brd_title.replace(' ', '_')}_{timestamp}.html"
        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Update BRD record with success status
        await nlp_collection.update_one(
            {"_id": ObjectId(brd_id)},
            {
                "$set": {
                    "html_file": file_path,
                    "html_filename": filename,
                    "processing_status": "completed",
                    "updated_at": datetime.now()
                }
            }
        )
        
        print(f"BRD processing completed for ID: {brd_id}")
        
    except Exception as e:
        # Update BRD record with error status
        await nlp_collection.update_one(
            {"_id": ObjectId(brd_id)},
            {
                "$set": {
                    "processing_status": "failed",
                    "processing_error": str(e),
                    "updated_at": datetime.now()
                }
            }
        )
        print(f"BRD processing failed for ID: {brd_id}, Error: {str(e)}")


def generate_fallback_html_old(title: str, content: str, gx1: dict) -> str:
    """
    Generate a basic fallback HTML if AI fails
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - GX1</title>
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Montserrat', Arial, Helvetica, sans-serif;
            font-size: 16px;
            color: {gx1['colors']['text_primary']}; /* text_primary */
            background-color: {gx1['colors']['surface_canvas']}; /* surface_canvas */
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px 60px 40px 60px;
            width: 85%; /* 75-85% content occupancy */
        }}
        
        .header {{
            position: relative;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid {gx1['colors']['brand_green']}; /* brand_green */
        }}
        
        .logo {{
            position: absolute;
            top: 0;
            right: 0;
            max-width: 180px;
            height: auto;
        }}
        
        h1 {{
            font-size: 32px;
            font-weight: 700;
            color: {gx1['colors']['text_primary']}; /* text_primary */
            margin-bottom: 20px;
        }}
        
        .content-section {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .form-field {{
            margin-bottom: 24px;
        }}
        
        .form-field label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            font-size: 14px;
            color: {gx1['colors']['text_primary']}; /* text_primary */
        }}
        
        .form-field input,
        .form-field textarea {{
            width: 100%;
            height: 40px; /* standard height */
            padding: 8px 12px;
            font-family: 'Montserrat', Arial, sans-serif;
            font-size: 14px;
            border: none;
            border-bottom: 1px solid {gx1['colors']['border_resting']}; /* border_resting */
            background: transparent;
            transition: border 0.2s;
        }}
        
        .form-field textarea {{
            height: 120px;
            resize: vertical;
        }}
        
        .form-field input:focus,
        .form-field textarea:focus {{
            outline: none;
            border-bottom: 2px solid {gx1['colors']['action_green']}; /* action_green */
            box-shadow: 0 2px 0 0 {gx1['colors']['action_green']}; /* focus ring */
        }}
        
        .btn-primary {{
            background-color: {gx1['colors']['action_green']}; /* action_green */
            color: white;
            border: none;
            padding: 12px 32px;
            font-family: 'Montserrat', Arial, sans-serif;
            font-size: 16px;
            font-weight: 600;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.2s;
        }}
        
        .btn-primary:hover {{
            background-color: {gx1['colors']['brand_green']}; /* brand_green */
        }}
        
        .btn-primary:focus {{
            outline: 2px solid {gx1['colors']['brand_green']}; /* focus outline */
            outline-offset: 2px;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 20px;
                width: 95%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <img src="{gx1['logo']['url']}" alt="GX1 Logo" class="logo">
        <div class="header">
            <h1>{title}</h1>
        </div>
        
        <div class="content-section">
            <h2>Requirements</h2>
            <p>{content}</p>
        </div>
        
        <div class="content-section">
            <h2>Generated Form</h2>
            <form>
                <div class="form-field">
                    <label for="name">Name</label>
                    <input type="text" id="name" name="name">
                </div>
                
                <div class="form-field">
                    <label for="email">Email</label>
                    <input type="email" id="email" name="email">
                </div>
                
                <div class="form-field">
                    <label for="notes">Additional Notes</label>
                    <textarea id="notes" name="notes"></textarea>
                </div>
                
                <button type="submit" class="btn-primary">Submit</button>
            </form>
        </div>
    </div>
</body>
</html>"""


def take_screenshot_sync(html_file_path: str, output_path: str):
    """
    Synchronous function to take screenshot using Playwright
    """
    from playwright.sync_api import sync_playwright
    
    html_file = Path(html_file_path).resolve()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file:///{html_file.as_posix()}")
        page.screenshot(path=output_path, full_page=True)
        browser.close()


@router.post("/html-to-image/{data_id}")
async def html_to_image(data_id: str):
    """
    Convert HTML file to PNG image based on data_id and upload to Cloudinary
    """
    try:
        # Step 1: Get the BRD record from MongoDB
        try:
            obj_id = ObjectId(data_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid data_id format: {str(e)}")
        
        brd_record = await nlp_collection.find_one({"_id": obj_id})
        
        if not brd_record:
            raise HTTPException(status_code=404, detail="BRD record not found")
        
        html_file_path = brd_record.get("html_file")
        
        if not html_file_path:
            raise HTTPException(status_code=404, detail="HTML file path not found in record")
        
        if not os.path.exists(html_file_path):
            raise HTTPException(status_code=404, detail=f"HTML file not found at path: {html_file_path}")
        
        # Step 2: Convert HTML to PNG using subprocess
        temp_png_path = os.path.join(tempfile.gettempdir(), f"ui_{data_id}.png")
        
        print(f"Converting HTML: {html_file_path}")
        print(f"Temp PNG path: {temp_png_path}")
        
        try:
            # Create a Python script to run in subprocess
            script_content = f'''
from pathlib import Path
from playwright.sync_api import sync_playwright

html_file = Path(r"{html_file_path}").resolve()
output_path = r"{temp_png_path}"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(f"file:///{{html_file.as_posix()}}")
    page.screenshot(path=output_path, full_page=True)
    browser.close()

print("Screenshot completed")
'''
            
            script_path = os.path.join(tempfile.gettempdir(), f"screenshot_{data_id}.py")
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Run the script in subprocess
            import subprocess
            result = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Clean up script
            if os.path.exists(script_path):
                os.remove(script_path)
            
            if result.returncode != 0:
                raise Exception(f"Screenshot process failed: {result.stderr}")
            
            print("Screenshot completed")
            
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Screenshot error: {type(e).__name__} - {str(e)}"
            )
        
        # Verify screenshot was created
        if not os.path.exists(temp_png_path):
            raise HTTPException(status_code=500, detail="Screenshot file was not created")
        
        # Step 3: Upload to Cloudinary
        try:
            print("Uploading to Cloudinary...")
            upload_result = cloudinary.uploader.upload(
                temp_png_path,
                folder="gx1_ui_previews",
                public_id=f"ui_{data_id}",
                overwrite=True,
                resource_type="image"
            )
            
            image_url = upload_result.get("secure_url")
            print(f"Upload successful: {image_url}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Cloudinary upload error: {str(e)}")
        
        # Step 4: Update MongoDB record with image URL
        try:
            await nlp_collection.update_one(
                {"_id": obj_id},
                {"$set": {"preview_image_url": image_url}}
            )
        except Exception as e:
            print(f"MongoDB update error: {str(e)}")
        
        # Step 5: Clean up temp file
        try:
            if os.path.exists(temp_png_path):
                os.remove(temp_png_path)
                print("Temp file cleaned up")
        except Exception as e:
            print(f"Cleanup error: {str(e)}")
        
        return {
            "message": "HTML converted to image successfully",
            "data_id": data_id,
            "image_url": image_url,
            "cloudinary_public_id": upload_result.get("public_id")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Unexpected error: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error: {type(e).__name__} - {str(e)}")


# ------------------------------
# GreenSolve API Endpoints
# ------------------------------

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
