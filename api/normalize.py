from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
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
clauses_collection = db.clauses
requirements_collection = db.requirements

router = APIRouter()

# OpenAI Client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "").strip())


# Pydantic Models
class GenerateRequirementRequest(BaseModel):
    clause_id: str


class GeneratedRequirement(BaseModel):
    requirement_title: str
    normalized_requirement_statement: str
    requirement_type: str
    functional_module: str
    actor_user_role: str
    priority: str
    business_rule: str
    acceptance_criteria: str


class SaveRequirementRequest(BaseModel):
    project_id: Optional[str] = None
    brd_id: str
    clause_id: str
    requirement_title: str
    normalized_requirement_statement: str
    requirement_type: str
    functional_module: str
    actor_user_role: str
    priority: str
    business_rule: str
    acceptance_criteria: str
    user_id: Optional[str] = None


# Helper Functions
async def generate_requirement_id() -> str:
    """Generate a unique requirement ID"""
    # Get the count of existing requirements to generate next ID
    count = await requirements_collection.count_documents({})
    return f"REQ-{str(count + 1).zfill(3)}"


async def normalize_clause_with_ai(clause_text: str, clause_id: str) -> dict:
    """
    Use OpenAI to normalize a clause into a structured requirement
    
    Args:
        clause_text: The clause text to normalize
        clause_id: The clause ID for reference
        
    Returns:
        Dictionary with normalized requirement fields
    """
    prompt = f"""You are a Business Analyst expert. Analyze the following requirement clause and extract structured information.

Clause ID: {clause_id}
Clause Text: {clause_text}

Extract and structure the following information in JSON format:
1. requirement_title: A concise title for this requirement
2. normalized_requirement_statement: A clear, precise requirement statement (should start with "The system shall...")
3. requirement_type: Either "Functional" or "Non-Functional"
4. functional_module: The module/area this requirement belongs to (e.g., "User Management", "Reporting", "Authentication")
5. actor_user_role: The primary user role who will use this feature (e.g., "Admin", "User", "Manager")
6. priority: Either "High", "Medium", or "Low"
7. business_rule: Any business rules associated with this requirement
8. acceptance_criteria: Clear, testable acceptance criteria

Return ONLY a JSON object with these exact field names. No additional text.

Example output format:
{{
    "requirement_title": "Automatic Employee ID Generation",
    "normalized_requirement_statement": "The system shall automatically generate a unique employee ID when a new employee is registered.",
    "requirement_type": "Functional",
    "functional_module": "Employee Registration",
    "actor_user_role": "HR Manager",
    "priority": "High",
    "business_rule": "Employee IDs must be unique and follow the format EMP-XXXX.",
    "acceptance_criteria": "Given a new employee registration, when the employee data is submitted, then a unique employee ID shall be generated and displayed."
}}"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert Business Analyst specializing in requirements engineering. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Try to parse the JSON response
        try:
            requirement_data = json.loads(content)
            return requirement_data
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                requirement_data = json.loads(json_match.group(1))
                return requirement_data
            else:
                raise ValueError(f"Failed to parse AI response as JSON: {content}")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating requirement: {str(e)}")


# API Endpoints

@router.post("/requirements/generate")
async def generate_requirement(request: GenerateRequirementRequest):
    """
    Generate a normalized requirement from a clause using AI
    Does not save to database - returns draft for BA review
    Updates clause status to "In Review"
    
    Args:
        request: Contains clause_id
        
    Returns:
        Generated requirement structure (draft)
    """
    try:
        # Load clause from database
        clause = await clauses_collection.find_one({"clause_id": request.clause_id})
        
        if not clause:
            raise HTTPException(status_code=404, detail=f"Clause not found: {request.clause_id}")
        
        clause_text = clause.get("text", "")
        
        if not clause_text:
            raise HTTPException(status_code=400, detail="Clause text is empty")
        
        # Update clause status to "In Review"
        await clauses_collection.update_one(
            {"clause_id": request.clause_id},
            {
                "$set": {
                    "status": "In Review",
                    "review_started_at": datetime.utcnow()
                }
            }
        )
        
        # Generate requirement using AI
        requirement_data = await normalize_clause_with_ai(clause_text, request.clause_id)
        
        return {
            "success": True,
            "clause_id": request.clause_id,
            "clause_text": clause_text,
            **requirement_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating requirement: {str(e)}")


@router.post("/requirements")
async def save_requirement(request: SaveRequirementRequest):
    """
    Save a reviewed and edited requirement to the database
    Updates the clause status to "Normalized"
    
    Args:
        request: Complete requirement data
        
    Returns:
        Saved requirement with generated requirement_id
    """
    try:
        # Generate unique requirement ID
        requirement_id = await generate_requirement_id()
        
        # Prepare requirement document
        requirement_doc = {
            "_id": ObjectId(),
            "requirement_id": requirement_id,
            "project_id": request.project_id,
            "brd_id": request.brd_id,
            "clause_id": request.clause_id,
            "user_id": request.user_id,
            "requirement_title": request.requirement_title,
            "normalized_requirement_statement": request.normalized_requirement_statement,
            "requirement_type": request.requirement_type,
            "functional_module": request.functional_module,
            "actor_user_role": request.actor_user_role,
            "priority": request.priority,
            "business_rule": request.business_rule,
            "acceptance_criteria": request.acceptance_criteria,
            "status": "Active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert requirement into database
        result = await requirements_collection.insert_one(requirement_doc)
        
        # Update clause status to "Normalized" and link requirement_id
        await clauses_collection.update_one(
            {"clause_id": request.clause_id},
            {
                "$set": {
                    "status": "Normalized",
                    "requirement_id": requirement_id,
                    "normalized_at": datetime.utcnow()
                }
            }
        )
        
        # Return saved requirement
        requirement_doc["_id"] = str(requirement_doc["_id"])
        
        return {
            "success": True,
            "message": "Requirement saved successfully",
            "requirement_id": requirement_id,
            "requirement": requirement_doc
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving requirement: {str(e)}")


@router.get("/requirements")
async def get_all_requirements():
    """
    Get all requirements from the database
    
    Returns:
        List of all requirements
    """
    try:
        requirements = []
        async for req in requirements_collection.find().sort("created_at", -1):
            req["_id"] = str(req["_id"])
            requirements.append(req)
        
        return {
            "success": True,
            "count": len(requirements),
            "requirements": requirements
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching requirements: {str(e)}")


@router.get("/requirements/brd/{brd_id}")
async def get_requirements_by_brd(brd_id: str):
    """
    Get all requirements for a specific BRD document
    
    Args:
        brd_id: BRD Document ID
        
    Returns:
        List of requirements for the BRD
    """
    try:
        requirements = []
        async for req in requirements_collection.find({"brd_id": brd_id}).sort("created_at", -1):
            req["_id"] = str(req["_id"])
            requirements.append(req)
        
        return {
            "success": True,
            "brd_id": brd_id,
            "count": len(requirements),
            "requirements": requirements
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching requirements: {str(e)}")


@router.get("/requirements/project/{project_id}")
async def get_requirements_by_project(project_id: str):
    """
    Get all requirements for a specific project
    
    Args:
        project_id: Project ID
        
    Returns:
        List of requirements for the project
    """
    try:
        requirements = []
        async for req in requirements_collection.find({"project_id": project_id}).sort("created_at", -1):
            req["_id"] = str(req["_id"])
            requirements.append(req)
        
        return {
            "success": True,
            "project_id": project_id,
            "count": len(requirements),
            "requirements": requirements
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching requirements: {str(e)}")


@router.get("/requirements/{requirement_id}")
async def get_requirement(requirement_id: str):
    """
    Get a specific requirement by requirement_id
    
    Args:
        requirement_id: Requirement ID (e.g., REQ-001)
        
    Returns:
        Requirement details
    """
    try:
        requirement = await requirements_collection.find_one({"requirement_id": requirement_id})
        
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")
        
        requirement["_id"] = str(requirement["_id"])
        
        return {
            "success": True,
            "requirement": requirement
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching requirement: {str(e)}")


@router.put("/requirements/{requirement_id}")
async def update_requirement(requirement_id: str, request: SaveRequirementRequest):
    """
    Update an existing requirement
    
    Args:
        requirement_id: Requirement ID (e.g., REQ-001)
        request: Updated requirement data
        
    Returns:
        Updated requirement
    """
    try:
        update_data = {
            "requirement_title": request.requirement_title,
            "normalized_requirement_statement": request.normalized_requirement_statement,
            "requirement_type": request.requirement_type,
            "functional_module": request.functional_module,
            "actor_user_role": request.actor_user_role,
            "priority": request.priority,
            "business_rule": request.business_rule,
            "acceptance_criteria": request.acceptance_criteria,
            "updated_at": datetime.utcnow()
        }
        
        result = await requirements_collection.update_one(
            {"requirement_id": requirement_id},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Requirement not found")
        
        updated_req = await requirements_collection.find_one({"requirement_id": requirement_id})
        updated_req["_id"] = str(updated_req["_id"])
        
        return {
            "success": True,
            "message": "Requirement updated successfully",
            "requirement": updated_req
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating requirement: {str(e)}")


@router.delete("/requirements/{requirement_id}")
async def delete_requirement(requirement_id: str):
    """
    Delete a requirement
    
    Args:
        requirement_id: Requirement ID (e.g., REQ-001)
        
    Returns:
        Success message
    """
    try:
        # Get requirement to find linked clause
        requirement = await requirements_collection.find_one({"requirement_id": requirement_id})
        
        if not requirement:
            raise HTTPException(status_code=404, detail="Requirement not found")
        
        # Delete requirement
        await requirements_collection.delete_one({"requirement_id": requirement_id})
        
        # Update clause status back to "Unprocessed" and remove requirement link
        clause_id = requirement.get("clause_id")
        if clause_id:
            await clauses_collection.update_one(
                {"clause_id": clause_id},
                {
                    "$set": {"status": "Unprocessed"},
                    "$unset": {"requirement_id": "", "normalized_at": ""}
                }
            )
        
        return {
            "success": True,
            "message": "Requirement deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting requirement: {str(e)}")
