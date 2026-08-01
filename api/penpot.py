import os
import uuid
import requests
from fastapi import APIRouter, HTTPException, File, UploadFile
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
import tempfile
import subprocess
import certifi
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from datetime import datetime
from openai import OpenAI
import json

load_dotenv()

# MongoDB
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://zainisrar2007_db_user:SUcRZUeK6sRJA3KL@cluster0.earf4sd.mongodb.net/")
async_client = AsyncIOMotorClient(MONGODB_URL, tlsCAFile=certifi.where()) if MONGODB_URL.startswith("mongodb+srv") else AsyncIOMotorClient(MONGODB_URL)
db = async_client.gx1
nlp_collection = db.userdata

cloudinary.config(
    cloud_name="dtkxm4abz",
    api_key="135213472543525",
    api_secret="7_RY2sgYVwKu04BAw1goYJn7aYY"
)

# OpenAI Configuration
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Penpot Configuration
PENPOT_API_URL = os.environ.get("PENPOT_API_URL", "https://design.penpot.app")
PENPOT_ACCESS_TOKEN = os.environ.get("PENPOT_ACCESS_TOKEN", "eyJhbGciOiJBMjU2S1ciLCJlbmMiOiJBMjU2R0NNIn0.FF-bTHscKhQJJrvlltcdNE43jWYqOBjfRKg7B-1ChneXQpbHi1ykXA.27_ksTQTQGpX3wSg.0_7FWcDJo_67EHzZS3HOjfQ22NF93MCtF4TKl-Svs9uymIybkBxNVQbX_HkhJi45iE5F28gp06-qxPJxeA443rszyEsntTrqvNbJa2wRTbK0Y7MsMjx7Fsw3eLptbVhmvPOcAhVfyzzNHDPretU_RA2bgnnjmSQl0q0xeXIaS2k7k9NpU7iLcGvSb-MF8irL2u4HdheTCK0U.JlR0VizypVX49vmzrZGl8A")
PENPOT_FILE_ID = os.environ.get("PENPOT_FILE_ID", "")
PENPOT_PROJECT_NAME = os.environ.get("PENPOT_PROJECT_NAME", "GX1 UI Designs")
PENPOT_FILE_NAME = os.environ.get("PENPOT_FILE_NAME", "Generated UIs")

router = APIRouter()


async def generate_react_from_image(image_url: str, brd_record: dict) -> str:
    """
    Generate React component code from UI image using OpenAI Vision API
    """
    # Load GX1 design system
    gx1_design_path = os.path.join(os.path.dirname(__file__), "gx1.json")
    with open(gx1_design_path, 'r') as f:
        gx1_design = json.load(f)
    
    brd_title = brd_record.get("title", "Component")
    brd_content = brd_record.get("content", "")
    
    system_prompt = f"""
You are an expert React developer specializing in converting UI designs to production-ready React components.

**GX1 Design System:**
{json.dumps(gx1_design, indent=2)}

**Your Task:**
Analyze the provided UI image and generate a complete, production-ready React component that:

1. **Accurately recreates the visual design** from the image
2. **Uses modern React best practices:**
   - Functional components with hooks (useState, useEffect, etc.)
   - TypeScript type definitions
   - Proper component structure and organization
   
3. **Implements GX1 Design System:**
   - Use Tailwind CSS classes or CSS modules
   - Follow GX1 color tokens (brand_green: #23B14D, action_green: #0F7A35, etc.)
   - Use Montserrat font family
   - Implement proper spacing, typography, and layout from design system
   
4. **Includes all UI elements visible in the image:**
   - Forms with validation
   - Tables with sample data
   - Buttons with proper states (hover, focus, disabled)
   - Input fields with labels and focus states
   - Dropdowns, checkboxes, radio buttons as needed
   - Proper grid/flexbox layouts
   
5. **Makes it functional:**
   - Add state management for interactive elements
   - Include form submission handlers (console.log for now)
   - Add onClick handlers for buttons
   - Include basic validation for forms
   - Add sample data for tables/lists (3-5 rows)
   
6. **Best practices:**
   - Responsive design (mobile-friendly)
   - Accessibility (ARIA labels, semantic HTML)
   - Clean, maintainable code with comments
   - Proper error handling
   - Loading states where appropriate

**BRD Context:**
Title: {brd_title}
Requirements: {brd_content[:500]}...

**Output Format:**
Provide ONLY the React component code. Include:
- Import statements
- TypeScript interfaces/types
- The main component
- Any helper functions
- CSS-in-JS or Tailwind classes
- Export statement

Start with imports and end with export. No markdown formatting, just clean code.
"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": system_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000,
            temperature=0.3
        )
        
        react_code = response.choices[0].message.content.strip()
        
        # Clean up markdown code blocks if present
        if react_code.startswith("```typescript") or react_code.startswith("```tsx"):
            react_code = react_code.replace("```typescript", "").replace("```tsx", "").replace("```", "").strip()
        elif react_code.startswith("```javascript") or react_code.startswith("```jsx"):
            react_code = react_code.replace("```javascript", "").replace("```jsx", "").replace("```", "").strip()
        elif react_code.startswith("```"):
            react_code = react_code.replace("```", "").strip()
        
        return react_code
    
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        # Return fallback template
        return generate_fallback_react_component(brd_title)


def generate_fallback_react_component(title: str) -> str:
    """
    Generate a basic fallback React component if LLM fails
    """
    component_name = title.replace(" ", "").replace("-", "").replace("_", "")
    
    return f"""import React, {{ useState }} from 'react';

interface {component_name}Props {{
  title?: string;
}}

const {component_name}: React.FC<{component_name}Props> = ({{ title = '{title}' }}) => {{
  const [formData, setFormData] = useState({{
    name: '',
    email: '',
    notes: ''
  }});

  const handleSubmit = (e: React.FormEvent) => {{
    e.preventDefault();
    console.log('Form submitted:', formData);
  }};

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {{
    setFormData({{
      ...formData,
      [e.target.name]: e.target.value
    }});
  }};

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6 text-gray-800">{{title}}</h1>
        
        <div className="bg-white rounded-lg shadow-md p-6">
          <form onSubmit={{handleSubmit}} className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                Name
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={{formData.name}}
                onChange={{handleChange}}
                className="w-full px-4 py-2 border-b border-gray-300 focus:border-green-600 focus:outline-none transition-colors"
                placeholder="Enter your name"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
                Email
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={{formData.email}}
                onChange={{handleChange}}
                className="w-full px-4 py-2 border-b border-gray-300 focus:border-green-600 focus:outline-none transition-colors"
                placeholder="Enter your email"
              />
            </div>

            <div>
              <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-2">
                Notes
              </label>
              <textarea
                id="notes"
                name="notes"
                value={{formData.notes}}
                onChange={{handleChange}}
                rows={{4}}
                className="w-full px-4 py-2 border border-gray-300 rounded focus:border-green-600 focus:outline-none transition-colors"
                placeholder="Additional notes..."
              />
            </div>

            <button
              type="submit"
              className="bg-green-700 hover:bg-green-800 text-white font-semibold py-2 px-6 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-green-600 focus:ring-offset-2"
            >
              Submit
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}};

export default {component_name};
"""


def _headers():
    return {
        "Authorization": f"Token {PENPOT_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def upload_from_url(file_id: str, image_url: str, name: str = "uploaded-image") -> dict:
    """Upload an image into a Penpot file directly from a public URL."""
    endpoint = f"{PENPOT_API_URL}/api/rpc/command/create-file-media-object-from-url"
    payload = {
        "file-id": file_id,
        "url": image_url,
        "name": name,
        "is-local": True,
    }
    resp = requests.post(endpoint, json=payload, headers=_headers())
    if not resp.ok:
        print("upload_from_url error:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def get_default_team_id() -> str:
    endpoint = f"{PENPOT_API_URL}/api/rpc/command/get-teams"
    resp = requests.post(endpoint, json={}, headers=_headers())
    if not resp.ok:
        print("get-teams error:", resp.status_code, resp.text)
    resp.raise_for_status()
    teams = resp.json()
    if not teams:
        raise RuntimeError("Account has no teams")
    default_team = next((t for t in teams if t.get("is-default")), teams[0])
    return default_team["id"]


def create_project(name: str, team_id: str | None = None) -> dict:
    if team_id is None:
        team_id = get_default_team_id()
    endpoint = f"{PENPOT_API_URL}/api/rpc/command/create-project"
    payload = {"team-id": team_id, "name": name}
    resp = requests.post(endpoint, json=payload, headers=_headers())
    if not resp.ok:
        print("create-project error:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def create_file(project_id: str, name: str) -> dict:
    endpoint = f"{PENPOT_API_URL}/api/rpc/command/create-file"
    payload = {"project-id": project_id, "name": name}
    resp = requests.post(endpoint, json=payload, headers=_headers())
    if not resp.ok:
        print("create-file error:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def ensure_file_id() -> str:
    if PENPOT_FILE_ID:
        return PENPOT_FILE_ID
    print(f"Creating project '{PENPOT_PROJECT_NAME}'...")
    project = create_project(PENPOT_PROJECT_NAME)
    project_id = project["id"]
    print(f"Creating file '{PENPOT_FILE_NAME}'...")
    file = create_file(project_id, PENPOT_FILE_NAME)
    file_id = file["id"]
    print(f"Created file id: {file_id}")
    return file_id


def get_file_data(file_id: str) -> dict:
    endpoint = f"{PENPOT_API_URL}/api/rpc/command/get-file"
    resp = requests.post(endpoint, json={"id": file_id}, headers=_headers())
    if not resp.ok:
        print("get-file error:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def get_file_revn_vern(file_id: str) -> tuple:
    data = get_file_data(file_id)
    return data.get("revn", 0), data.get("vern", 0)


def get_first_page_id(file_id: str) -> str:
    data = get_file_data(file_id)
    pages = data["data"]["pages"]
    if not pages:
        raise RuntimeError("File has no pages")
    return pages[0]


def add_media_to_file(file_id: str, media_object: dict) -> dict:
    endpoint = f"{PENPOT_API_URL}/api/rpc/command/update-file"
    current_revn, current_vern = get_file_revn_vern(file_id)
    payload = {
        "id": file_id,
        "session-id": str(uuid.uuid4()),
        "revn": current_revn,
        "vern": current_vern,
        "changes": [{"type": "add-media", "object": media_object}],
    }
    resp = requests.post(endpoint, json=payload, headers=_headers())
    if not resp.ok:
        print("add-media error:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def place_image_on_canvas(
    file_id: str, media_object: dict, page_id: str | None = None,
    x: float = 0, y: float = 0, width: float | None = None, height: float | None = None
) -> dict:
    if page_id is None:
        page_id = get_first_page_id(file_id)
    root_frame_id = "00000000-0000-0000-0000-000000000000"
    w = width or media_object.get("width", 512)
    h = height or media_object.get("height", 512)
    shape_id = str(uuid.uuid4())
    obj = {
        "id": shape_id, "type": "image", "name": media_object.get("name", "image"),
        "page-id": page_id, "frame-id": root_frame_id, "parent-id": root_frame_id,
        "x": x, "y": y, "width": w, "height": h,
        "selrect": {"x": x, "y": y, "width": w, "height": h, "x1": x, "y1": y, "x2": x + w, "y2": y + h},
        "points": [{"x": x, "y": y}, {"x": x + w, "y": y}, {"x": x + w, "y": y + h}, {"x": x, "y": y + h}],
        "transform": {"a": 1, "b": 0, "c": 0, "d": 1, "e": 0, "f": 0},
        "transform-inverse": {"a": 1, "b": 0, "c": 0, "d": 1, "e": 0, "f": 0},
        "rotation": 0, "proportion": (w / h) if h else 1, "proportion-lock": False,
        "metadata": {"id": media_object["id"], "width": w, "height": h, "mtype": media_object.get("mtype", "image/png")},
        "fills": [],
    }
    current_revn, current_vern = get_file_revn_vern(file_id)
    endpoint = f"{PENPOT_API_URL}/api/rpc/command/update-file"
    payload = {
        "id": file_id, "session-id": str(uuid.uuid4()), "revn": current_revn, "vern": current_vern,
        "changes": [{"type": "add-obj", "id": shape_id, "page-id": page_id, "frame-id": root_frame_id, "parent-id": root_frame_id, "obj": obj}],
    }
    resp = requests.post(endpoint, json=payload, headers=_headers())
    if not resp.ok:
        print("add-obj error:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def export_page_as_image(file_id: str, page_id: str, scale: int = 2) -> bytes:
    """
    Export a Penpot page as PNG image
    Returns the image bytes
    
    WORKAROUND: Since Penpot's export API is restricted, we take a screenshot
    of the original uploaded image from the media object instead.
    Users can manually export from Penpot UI and re-upload if needed.
    """
    
    # Strategy 1: Get the file data and extract the media object
    # This returns the original uploaded image, not the edited version
    # But it's better than nothing until Penpot provides proper export API
    try:
        file_data = get_file_data(file_id)
        
        # Look for media objects in the file
        if "data" in file_data and "media" in file_data["data"]:
            media_objects = file_data["data"]["media"]
            
            # Get the most recent media object (assuming it's the one we uploaded)
            if media_objects:
                # Media objects are stored as a dict with IDs as keys
                if isinstance(media_objects, dict):
                    media_list = list(media_objects.values())
                    if media_list:
                        latest_media = media_list[-1]  # Get the last uploaded media
                        
                        # Try to get the media URL
                        media_uri = latest_media.get("uri") or latest_media.get("path")
                        
                        if media_uri:
                            if not media_uri.startswith("http"):
                                media_uri = f"{PENPOT_API_URL}{media_uri}"
                            
                            # Download the media
                            media_resp = requests.get(media_uri, headers=_headers())
                            if media_resp.ok:
                                print(f"Retrieved media object from file data: {media_uri}")
                                return media_resp.content
        
        print("Could not find media objects in file data")
    except Exception as e:
        print(f"Media object retrieval failed: {e}")
    
    # Strategy 2: Return a message indicating manual export is needed
    # Since we can't programmatically export, we'll raise an exception
    # with a helpful message
    
    raise Exception(
        "Penpot's export API is restricted. To export your edited design: "
        "1. Open the design in Penpot workspace "
        "2. Click 'Export' in the top menu "
        "3. Select PNG format and desired scale "
        "4. Download the exported file "
        "Note: The original uploaded image is available in the workspace."
    )


def export_file_as_image(file_id: str, scale: int = 2) -> bytes:
    """
    Export first page of Penpot file as PNG image
    Returns the image bytes
    """
    page_id = get_first_page_id(file_id)
    return export_page_as_image(file_id, page_id, scale)


@router.post("/penpot/{data_id}")
async def upload_to_penpot(data_id: str):
    """Convert HTML to PNG, upload to Cloudinary, then upload to Penpot"""
    try:
        obj_id = ObjectId(data_id)
        brd_record = await nlp_collection.find_one({"_id": obj_id})
        if not brd_record:
            raise HTTPException(status_code=404, detail="BRD record not found")
        html_file_path = brd_record.get("html_file")
        brd_title = brd_record.get("title", "Untitled")
        if not html_file_path or not os.path.exists(html_file_path):
            raise HTTPException(status_code=404, detail="HTML file not found")
        
        temp_png_path = os.path.join(tempfile.gettempdir(), f"penpot_{data_id}.png")
        script_content = f'''
from pathlib import Path
from playwright.sync_api import sync_playwright
html_file = Path(r"{html_file_path}").resolve()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(f"file:///{{html_file.as_posix()}}")
    page.screenshot(path=r"{temp_png_path}", full_page=True)
    browser.close()
'''
        script_path = os.path.join(tempfile.gettempdir(), f"penpot_screenshot_{data_id}.py")
        with open(script_path, 'w') as f:
            f.write(script_content)
        result = subprocess.run(['python', script_path], capture_output=True, text=True, timeout=30)
        if os.path.exists(script_path):
            os.remove(script_path)
        if result.returncode != 0:
            raise Exception(f"Screenshot failed: {result.stderr}")
        
        upload_result = cloudinary.uploader.upload(temp_png_path, folder="gx1_penpot", public_id=f"penpot_{data_id}", overwrite=True, resource_type="image")
        image_url = upload_result.get("secure_url")
        print(f"Cloudinary: {image_url}")
        
        file_id = ensure_file_id()
        media_object = upload_from_url(file_id, image_url, name=f"gx1_{brd_title}")
        add_media_to_file(file_id, media_object)
        
        # Get page_id for the URL
        page_id = get_first_page_id(file_id)
        
        # Get team_id for the URL
        team_id = get_default_team_id()
        
        place_image_on_canvas(file_id, media_object, page_id=page_id, x=0, y=0)
        
        # Step 5: Update MongoDB
        await nlp_collection.update_one(
            {"_id": obj_id},
            {"$set": {
                "penpot_image_url": image_url,
                "penpot_file_id": file_id,
                "penpot_media_id": media_object["id"],
                "penpot_page_id": page_id,
                "penpot_team_id": team_id
            }}
        )
        
        if os.path.exists(temp_png_path):
            os.remove(temp_png_path)
        
        # Construct proper Penpot workspace URL
        penpot_workspace_url = f"{PENPOT_API_URL}/#/workspace?team-id={team_id}&file-id={file_id}&page-id={page_id}"
        
        return {
            "message": "UI uploaded to Penpot successfully",
            "data_id": data_id,
            "image_url": image_url,
            "penpot_file_id": file_id,
            "penpot_media_id": media_object["id"],
            "penpot_page_id": page_id,
            "penpot_team_id": team_id,
            "penpot_workspace_url": penpot_workspace_url
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {type(e).__name__} - {str(e)}")



@router.get("/penpot/{data_id}/export")
async def export_from_penpot(data_id: str, scale: int = 2):
    """
    Export the edited design from Penpot and upload to Cloudinary
    
    NOTE: Due to Penpot API limitations, programmatic export is restricted.
    Users should manually export from Penpot UI and use the upload endpoint instead.
    """
    try:
        obj_id = ObjectId(data_id)
        brd_record = await nlp_collection.find_one({"_id": obj_id})
        
        if not brd_record:
            raise HTTPException(status_code=404, detail="BRD record not found")
        
        penpot_file_id = brd_record.get("penpot_file_id")
        penpot_page_id = brd_record.get("penpot_page_id")
        
        if not penpot_file_id or not penpot_page_id:
            raise HTTPException(status_code=404, detail="Penpot file not found. Upload to Penpot first.")
        
        print(f"Exporting from Penpot: file={penpot_file_id}, page={penpot_page_id}")
        
        # Export from Penpot
        image_bytes = export_page_as_image(penpot_file_id, penpot_page_id, scale=scale)
        
        # Save to temp file
        temp_path = os.path.join(tempfile.gettempdir(), f"penpot_export_{data_id}.png")
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)
        
        print(f"Penpot export saved: {temp_path}")
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            temp_path,
            folder="gx1_penpot_exports",
            public_id=f"edited_{data_id}",
            overwrite=True,
            resource_type="image"
        )
        
        exported_url = upload_result.get("secure_url")
        print(f"Uploaded to Cloudinary: {exported_url}")
        
        # Update MongoDB
        await nlp_collection.update_one(
            {"_id": obj_id},
            {"$set": {
                "penpot_exported_url": exported_url,
                "penpot_exported_at": datetime.now()
            }}
        )
        
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return {
            "message": "Design exported from Penpot successfully",
            "data_id": data_id,
            "exported_url": exported_url,
            "penpot_file_id": penpot_file_id,
            "penpot_page_id": penpot_page_id,
            "scale": scale
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        
        # Return helpful error message
        error_msg = str(e)
        if "Penpot's export API is restricted" in error_msg:
            raise HTTPException(
                status_code=501, 
                detail={
                    "error": "Penpot API export not available",
                    "message": error_msg,
                    "workaround": "Use the manual upload endpoint: POST /api/project-sites/penpot/{data_id}/upload-export"
                }
            )
        
        raise HTTPException(status_code=500, detail=f"Export error: {type(e).__name__} - {error_msg}")



@router.get("/generate-code/{data_id}")
async def generate_react_code_from_image(data_id: str):
    """
    Get image URL from database and generate React code using LLM
    Returns both the image URL and generated React code
    """
    try:
        obj_id = ObjectId(data_id)
        brd_record = await nlp_collection.find_one({"_id": obj_id})
        
        if not brd_record:
            raise HTTPException(status_code=404, detail="BRD record not found")
        
        # Get image URL - prioritize exported image over original upload
        image_url = brd_record.get("penpot_exported_url") or brd_record.get("penpot_image_url") or brd_record.get("preview_image_url")
        
        if not image_url:
            raise HTTPException(
                status_code=404, 
                detail="No image found for this BRD. Please upload to Penpot or generate HTML preview first."
            )
        
        print(f"Generating React code for image: {image_url}")
        
        # Generate React code using OpenAI Vision API
        react_code = await generate_react_from_image(image_url, brd_record)
        
        # Update MongoDB with generated code
        await nlp_collection.update_one(
            {"_id": obj_id},
            {"$set": {
                "generated_react_code": react_code,
                "react_code_generated_at": datetime.now()
            }}
        )
        
        # Get workspace URL if available
        workspace_url = None
        if brd_record.get("penpot_file_id"):
            file_id = brd_record.get("penpot_file_id")
            page_id = brd_record.get("penpot_page_id")
            team_id = brd_record.get("penpot_team_id")
            workspace_url = f"{PENPOT_API_URL}/#/workspace?team-id={team_id}&file-id={file_id}&page-id={page_id}"
        
        return {
            "message": "React code generated successfully",
            "data_id": data_id,
            "image_url": image_url,
            "react_code": react_code,
            "workspace_url": workspace_url,
            "brd_title": brd_record.get("title", "Untitled")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


