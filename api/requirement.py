from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import certifi
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# MongoDB Configuration
MONGODB_URL = "mongodb+srv://zainisrar_db_user:zain123@cluster0.myxypuf.mongodb.net/gx1"
if not MONGODB_URL:
    raise ValueError("MONGODB_URL environment variable is not set")
async_client = AsyncIOMotorClient(MONGODB_URL, tlsCAFile=certifi.where()) if MONGODB_URL.startswith("mongodb+srv") else AsyncIOMotorClient(MONGODB_URL)
db = async_client.gx1
requirements_collection = db.requirements
layout_cache_collection = db.layout_recommendations

router = APIRouter()

# OpenAI Client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# Pydantic Models
class ScreenPreview(BaseModel):
    name: str
    svg: str
    requirements: List[str]


# Helper Functions
async def get_normalized_requirements(brd_id: str) -> List[Dict]:
    """Get all active requirements for a BRD"""
    requirements = []
    async for req in requirements_collection.find({
        "brd_id": brd_id,
        "status": "Active"
    }).sort("requirement_id", 1):
        requirements.append(req)
    return requirements


def format_requirements_for_ai(requirements: List[Dict]) -> str:
    """Format requirements into a string for AI processing"""
    formatted = []
    for req in requirements:
        req_line = f"{req.get('requirement_id')}: {req.get('normalized_requirement_statement')}"
        if req.get('requirement_type'):
            req_line += f" [Type: {req.get('requirement_type')}]"
        if req.get('functional_module'):
            req_line += f" [Module: {req.get('functional_module')}]"
        if req.get('actor_user_role'):
            req_line += f" [Actor: {req.get('actor_user_role')}]"
        formatted.append(req_line)
    return "\n".join(formatted)


async def generate_architecture(requirements_text: str) -> Dict:
    """
    Step 1: Generate architecture (screens, groupings, layout options)
    NO SVG generation in this step
    """
    prompt = f"""Analyze these requirements and provide application architecture recommendations.

REQUIREMENTS:
{requirements_text}

Return JSON with:
{{
  "estimated_screens": <number>,
  "layout_options": [
    {{ "id": "OPTION-1", "name": "<name>", "description": "<desc>", "confidence": <85-95>, "pros": [...], "cons": [...] }},
    {{ "id": "OPTION-2", "name": "<name>", "description": "<desc>", "confidence": <70-85>, "pros": [...], "cons": [...] }},
    {{ "id": "OPTION-3", "name": "<name>", "description": "<desc>", "confidence": <60-75>, "pros": [...], "cons": [...] }}
  ],
  "screen_groups": [
    {{ "screen": "<name>", "requirements": ["REQ-001", ...], "description": "<what it does>" }}
  ],
  "reusable_components": [
    {{ "name": "<name>", "type": "<form|table|card|etc>", "description": "<desc>", "requirements": [...] }}
  ]
}}

GUIDELINES:
- Estimate realistic screen count
- Group 2-6 requirements per screen
- Option 1: Traditional (sidebar) - highest confidence
- Option 2: Modern (top nav) - medium confidence  
- Option 3: Alternative (dashboard) - lower confidence
- NO SVG in this response

Return ONLY valid JSON."""

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a UX/UI architect. Return JSON only, no SVG."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=3000
    )
    
    content = response.choices[0].message.content.strip()
    
    # Parse JSON
    if content.startswith("```"):
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            content = content.replace("```json", "").replace("```", "").strip()
    
    return json.loads(content)


async def generate_layout_previews(layout_option: Dict, screen_groups: List[Dict]) -> Dict:
    """
    Step 2: Generate application shell + individual screen SVGs for a layout option
    """
    screen_details = "\n".join([
        f"{s.get('screen')}: {s.get('description')} (Requirements: {', '.join(s.get('requirements', []))})"
        for s in screen_groups
    ])
    
    prompt = f"""Generate SVG wireframes for this layout and all screens.

LAYOUT: {layout_option.get('name')} - {layout_option.get('description')}

SCREENS:
{screen_details}

Return JSON:
{{
  "option": "{layout_option.get('id')}",
  "application_shell": "<SVG 800x600 showing navigation structure>",
  "screens": [
    {{ "name": "<screen name>", "svg": "<SVG 800x600 showing FULL app with this screen's content>", "requirements": [...] }}
  ]
}}

SVG RULES:
1. Application Shell: Show nav structure + placeholder content
2. Each Screen SVG: Show FULL app (nav + this screen's specific content)
3. Use wireframe style: #f0f0f0 backgrounds, #333 borders, #666 text
4. Label all components
5. Match layout option style

EXAMPLE SHELL:
<svg width="800" height="600" xmlns="http://www.w3.org/2000/svg">
  <rect width="800" height="600" fill="#fff"/>
  <rect x="0" y="0" width="200" height="600" fill="#f0f0f0" stroke="#333" stroke-width="1"/>
  <text x="20" y="30" font-family="Arial" font-size="14" fill="#333">Sidebar</text>
  <rect x="200" y="0" width="600" height="60" fill="#f8f8f8" stroke="#333" stroke-width="1"/>
  <text x="220" y="35" font-family="Arial" font-size="14" fill="#333">Header</text>
  <rect x="200" y="60" width="600" height="540" fill="#fff" stroke="#ddd" stroke-width="1"/>
</svg>

Return ONLY valid JSON."""

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a wireframe expert. Generate complete SVG wireframes in JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=8000
    )
    
    content = response.choices[0].message.content.strip()
    
    # Parse JSON
    if content.startswith("```"):
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            content = content.replace("```json", "").replace("```", "").strip()
    
    return json.loads(content)


# API Endpoints

@router.post("/architecture/{brd_id}")
async def generate_architecture_recommendation(brd_id: str):
    """
    STEP 1: Generate architecture (screens, groupings, layout options) - NO SVG
    """
    try:
        requirements = await get_normalized_requirements(brd_id)
        if not requirements:
            raise HTTPException(status_code=404, detail=f"No requirements found for BRD: {brd_id}")
        
        requirements_text = format_requirements_for_ai(requirements)
        architecture = await generate_architecture(requirements_text)
        
        # Cache architecture
        await layout_cache_collection.update_one(
            {"brd_id": brd_id},
            {"$set": {
                "brd_id": brd_id,
                "architecture": architecture,
                "total_requirements": len(requirements),
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
        
        return {
            "success": True,
            "brd_id": brd_id,
            "total_requirements": len(requirements),
            "estimated_screens": architecture.get("estimated_screens", 0),
            "layout_options": architecture.get("layout_options", []),
            "screen_groups": architecture.get("screen_groups", []),
            "reusable_components": architecture.get("reusable_components", []),
            "message": f"Architecture generated for {len(requirements)} requirements"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/layout-previews/{brd_id}/{option_id}")
async def generate_layout_preview(brd_id: str, option_id: str):
    """
    STEP 2: Generate application shell + screen SVGs for a specific layout option
    """
    try:
        cached = await layout_cache_collection.find_one({"brd_id": brd_id})
        if not cached or "architecture" not in cached:
            raise HTTPException(status_code=404, detail=f"Generate architecture first: POST /architecture/{brd_id}")
        
        architecture = cached["architecture"]
        layout_option = next((o for o in architecture.get("layout_options", []) if o.get("id") == option_id), None)
        
        if not layout_option:
            available = [o.get('id') for o in architecture.get('layout_options', [])]
            raise HTTPException(status_code=404, detail=f"{option_id} not found. Available: {available}")
        
        previews = await generate_layout_previews(layout_option, architecture.get("screen_groups", []))
        
        # Cache previews
        await layout_cache_collection.update_one(
            {"brd_id": brd_id},
            {"$set": {
                f"previews.{option_id}": previews,
                f"previews.{option_id}_generated_at": datetime.utcnow()
            }}
        )
        
        return {
            "success": True,
            "brd_id": brd_id,
            "option": option_id,
            "application_shell": previews.get("application_shell"),
            "screens": previews.get("screens", []),
            "message": f"Generated {len(previews.get('screens', []))} screen previews"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/layout-previews/{brd_id}/{option_id}")
async def get_layout_preview(brd_id: str, option_id: str):
    """Get cached layout previews"""
    try:
        cached = await layout_cache_collection.find_one({"brd_id": brd_id})
        if not cached or "previews" not in cached or option_id not in cached["previews"]:
            raise HTTPException(status_code=404, detail=f"Generate previews first: POST /layout-previews/{brd_id}/{option_id}")
        
        previews = cached["previews"][option_id]
        return {
            "success": True,
            "brd_id": brd_id,
            "option": option_id,
            "application_shell": previews.get("application_shell"),
            "screens": previews.get("screens", []),
            "message": "Retrieved cached previews"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
