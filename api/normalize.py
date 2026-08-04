from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import certifi
from dotenv import load_dotenv
import httpx

load_dotenv()

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://zainisrar2007_db_user:SUcRZUeK6sRJA3KL@cluster0.earf4sd.mongodb.net/")
async_client = AsyncIOMotorClient(MONGODB_URL, tlsCAFile=certifi.where()) if MONGODB_URL.startswith("mongodb+srv") else AsyncIOMotorClient(MONGODB_URL)
db = async_client.gx1
brd_normalize_collection = db.brd_normalize
normalized_requirements_collection = db.normalized_requirements

router = APIRouter()

# ------------------------------
# Models
# ------------------------------

class BRDClause(BaseModel):
    source_ref: str  # e.g., "BRD-S3.2.1"
    clause_statement: str  # The actual clause text
    page: int
    type_suggestion: str  # e.g., "Functional", "Security", "Non-Functional"
    status: str  # "Unprocessed", "In Review", "Normalised", "Needs Clarification"
    section: Optional[str] = None  # e.g., "3.2 Task Management"
    extracted_keywords: Optional[List[str]] = None  # e.g., ["task creation", "owner", "priority"]

class BRDRequestByProjectId(BaseModel):
    brd_title: str
    clauses: List[BRDClause]
    project_id: int  # GSolve project ID (primary identifier)

class NormalizedRequirement(BaseModel):
    # Auto-generated field
    requirement_id: Optional[str] = None  # e.g., "NRM-REQ-014" (auto-generated if not provided)
    
    # Basic Information
    requirement_title: str  # e.g., "Task Creation with Owner, Priority and Due Date"
    normalised_requirement_statement: str  # The normalized statement
    
    # Flags
    is_traceable: bool = False
    is_testable: bool = False
    needs_clarification: bool = False
    
    # Classification
    requirement_type: str  # e.g., "Functional", "Non-Functional", "Security"
    functional_module: str  # e.g., "Task Management"
    actor_user_role: str  # e.g., "Task Manager"
    
    # Details
    priority: str  # e.g., "High", "Medium", "Low"
    business_rule: Optional[str] = None
    acceptance_criteria: str
    
    # Relationships
    dependencies: Optional[str] = None  # e.g., "User Management, Calendar Service"
    owner: str  # e.g., "Rohit Sharma (BA)"
    status: str  # e.g., "In Review", "Draft", "Ready"
    
    # Traceability to Source BRD
    source_section: Optional[str] = None  # e.g., "3.2 Task Management"
    source_page: Optional[int] = None  # e.g., 12
    source_clause: Optional[str] = None  # e.g., "BRD-S3.2.1"
    source_confidence: Optional[str] = None  # e.g., "92%"
    
    # Linking to original BRD
    brd_id: Optional[str] = None  # Reference to original BRD document
    project_id: Optional[int] = None  # GSolve project ID

class ClauseUpdate(BaseModel):
    status: str  # New status to update

class BRDResponse(BaseModel):
    id: str
    brd_title: str
    project_id: int  # GSolve project ID
    project_code: str
    project_name: str
    clauses: List[dict]
    total_clauses: int
    status_counts: dict
    created_at: datetime
    updated_at: datetime

# ------------------------------
# Endpoints
# ------------------------------

@router.post("/add-brd", response_model=dict)
async def add_brd_by_project_id(brd_request: BRDRequestByProjectId):
    """
    Add BRD data based on GSolve project ID.
    Fetches project details from GSolve API and associates BRD with that project.
    
    Request body:
    {
        "brd_title": "BRD HRM Employee Registration",
        "project_id": 1,
        "clauses": [
            {
                "source_ref": "BRD-S3.2.1",
                "clause_statement": "The system shall allow task creation with owner, priority and due date.",
                "page": 12,
                "type_suggestion": "Functional",
                "status": "In Review",
                "section": "3.2 Task Management",
                "extracted_keywords": ["task creation", "owner", "priority", "due date"]
            }
        ]
    }
    """
    try:
        # Step 1: Fetch project details from GSolve API
        gsolve_url = "https://app-gsolve.green.com.pg/project_list/digitall/"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(gsolve_url)
                response.raise_for_status()
                gsolve_response = response.json()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Failed to fetch GSolve project list: {str(e)}"
            )
        
        # Step 2: Find the specific project by ID
        # Handle two possible response structures:
        # 1. {"data": {"code": "001", "project_list": [...]}}
        # 2. {"code": "001", "project_list": [...]}
        
        # Check if response has nested "data" key
        if "data" in gsolve_response and isinstance(gsolve_response["data"], dict):
            gsolve_data = gsolve_response["data"]
        else:
            gsolve_data = gsolve_response
        
        project_list = gsolve_data.get("project_list", [])
        
        if not project_list:
            raise HTTPException(
                status_code=503,
                detail=f"GSolve API returned empty project list. Full response: {gsolve_response}"
            )
        
        project = None
        
        for proj in project_list:
            # Compare as both int and string to handle API inconsistencies
            proj_id = proj.get("id")
            if proj_id == brd_request.project_id or str(proj_id) == str(brd_request.project_id):
                project = proj
                break
        
        if not project:
            available_ids = [p.get('id') for p in project_list]
            raise HTTPException(
                status_code=404,
                detail=f"Project with ID {brd_request.project_id} not found in GSolve. Available project IDs: {available_ids}"
            )
        
        # Step 3: Extract project details
        project_id = project.get("id")
        project_code = project.get("project_code")
        project_name = project.get("project_name")
        customer = project.get("customer")
        currency = project.get("currency_name")
        start_date = project.get("start_date")
        target_end_date = project.get("target_end_date")
        project_status = project.get("project_status", "")
        project_type = project.get("project_type", "")
        business_domain = project.get("business_domain", "")
        sub_domain = project.get("sub_domain", "")
        manager = project.get("manager", "")
        budget = project.get("budget", "")
        priority = project.get("priority", "")
        contract_reference = project.get("contract_reference", "")
        last_updated = project.get("last_updated", "")
        updated_by = project.get("updated_by", "")
        
        # Step 4: Count clauses by status
        status_counts = {
            "All": len(brd_request.clauses),
            "Unprocessed": 0,
            "In Review": 0,
            "Normalised": 0,
            "Needs Clarification": 0
        }
        
        for clause in brd_request.clauses:
            status = clause.status
            if status in status_counts:
                status_counts[status] += 1
        
        # Step 5: Prepare document for MongoDB with full GSolve project details
        brd_document = {
            # BRD Information
            "brd_title": brd_request.brd_title,
            "clauses": [clause.dict() for clause in brd_request.clauses],
            "total_clauses": len(brd_request.clauses),
            "status_counts": status_counts,
            
            # GSolve Project Information (ID is primary)
            "project_id": project_id,
            "project_code": project_code,
            "project_name": project_name,
            "customer": customer,
            "currency": currency,
            "start_date": start_date,
            "target_end_date": target_end_date,
            "project_status": project_status,
            "project_type": project_type,
            "business_domain": business_domain,
            "sub_domain": sub_domain,
            "manager": manager,
            "budget": budget,
            "priority": priority,
            "contract_reference": contract_reference,
            "last_updated": last_updated,
            "updated_by": updated_by,
            
            # Full project data for reference
            "gsolve_project_data": project,
            
            # Timestamps
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Step 6: Insert into MongoDB
        result = await brd_normalize_collection.insert_one(brd_document)
        
        return {
            "message": "BRD data added successfully with GSolve project details",
            "brd_id": str(result.inserted_id),
            "total_clauses": len(brd_request.clauses),
            "status_counts": status_counts,
            "project_details": {
                "project_id": project_id,
                "project_code": project_code,
                "project_name": project_name,
                "customer": customer,
                "start_date": start_date,
                "target_end_date": target_end_date,
                "project_status": project_status,
                "project_type": project_type,
                "business_domain": business_domain,
                "manager": manager,
                "priority": priority
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding BRD data: {str(e)}")


@router.get("/get-brd/{brd_id}", response_model=BRDResponse)
async def get_brd_data(brd_id: str):
    """
    Get BRD data by ID
    """
    try:
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(brd_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid BRD ID format")
        
        # Fetch from MongoDB
        brd_data = await brd_normalize_collection.find_one({"_id": obj_id})
        
        if not brd_data:
            raise HTTPException(status_code=404, detail="BRD not found")
        
        # Convert ObjectId to string
        brd_data["id"] = str(brd_data.pop("_id"))
        
        return brd_data
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching BRD data: {str(e)}")


@router.get("/get-all-brds")
async def get_all_brds(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return")
):
    """
    Get all BRD records with pagination
    """
    try:
        # Count total documents
        total = await brd_normalize_collection.count_documents({})
        
        # Fetch documents with pagination
        cursor = brd_normalize_collection.find({}).skip(skip).limit(limit).sort("created_at", -1)
        brds = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for brd in brds:
            brd["id"] = str(brd.pop("_id"))
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "data": brds
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching BRDs: {str(e)}")


@router.get("/get-brds-by-project/{project_id}")
async def get_brds_by_project_id(
    project_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return")
):
    """
    Get all BRD records for a specific GSolve project ID
    """
    try:
        # Count total documents for this project (handle both int and string IDs)
        query = {"$or": [{"project_id": project_id}, {"project_id": str(project_id)}]}
        total = await brd_normalize_collection.count_documents(query)
        
        if total == 0:
            return {
                "message": f"No BRDs found for project ID {project_id}",
                "total": 0,
                "skip": skip,
                "limit": limit,
                "data": []
            }
        
        # Fetch documents with pagination
        cursor = brd_normalize_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        brds = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for brd in brds:
            brd["id"] = str(brd.pop("_id"))
        
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "project_id": project_id,
            "data": brds
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching BRDs: {str(e)}")


@router.get("/get-all-normalize-brds-by-project/{project_id}")
async def get_all_normalize_brds_by_project_id(project_id: int):
    """
    Get all normalized BRD data for a specific GSolve project ID.
    Returns complete summary with status counts and all clauses grouped by status.
    """
    try:
        # Query for all BRDs for this project (handle both int and string IDs)
        query = {"$or": [{"project_id": project_id}, {"project_id": str(project_id)}]}
        
        # Count total BRDs
        total_brds = await brd_normalize_collection.count_documents(query)
        
        if total_brds == 0:
            return {
                "message": f"No BRDs found for project ID {project_id}",
                "project_id": project_id,
                "total_brds": 0,
                "overall_status_counts": {
                    "all": 0,
                    "unprocessed": 0,
                    "in_review": 0,
                    "normalised": 0,
                    "needs_clarification": 0
                },
                "brds": []
            }
        
        # Fetch all BRDs for this project
        cursor = brd_normalize_collection.find(query).sort("created_at", -1)
        brds = await cursor.to_list(length=None)
        
        # Initialize overall counters
        overall_counts = {
            "all": 0,
            "unprocessed": 0,
            "in_review": 0,
            "normalised": 0,
            "needs_clarification": 0
        }
        
        # Process each BRD
        processed_brds = []
        
        for brd in brds:
            brd_id = str(brd.pop("_id"))
            all_clauses = brd.get("clauses", [])
            
            # Separate clauses by status
            unprocessed_clauses = [c for c in all_clauses if c.get("status") == "Unprocessed"]
            in_review_clauses = [c for c in all_clauses if c.get("status") == "In Review"]
            normalised_clauses = [c for c in all_clauses if c.get("status") == "Normalised"]
            needs_clarification_clauses = [c for c in all_clauses if c.get("status") == "Needs Clarification"]
            
            # Update overall counts
            overall_counts["all"] += len(all_clauses)
            overall_counts["unprocessed"] += len(unprocessed_clauses)
            overall_counts["in_review"] += len(in_review_clauses)
            overall_counts["normalised"] += len(normalised_clauses)
            overall_counts["needs_clarification"] += len(needs_clarification_clauses)
            
            # Prepare BRD summary
            brd_summary = {
                "brd_id": brd_id,
                "brd_title": brd.get("brd_title"),
                "project_id": brd.get("project_id"),
                "project_code": brd.get("project_code"),
                "project_name": brd.get("project_name"),
                "customer": brd.get("customer"),
                "created_at": brd.get("created_at"),
                "updated_at": brd.get("updated_at"),
                
                # Status counts for this BRD
                "status_counts": {
                    "all": len(all_clauses),
                    "unprocessed": len(unprocessed_clauses),
                    "in_review": len(in_review_clauses),
                    "normalised": len(normalised_clauses),
                    "needs_clarification": len(needs_clarification_clauses)
                },
                
                # All clauses grouped by status
                "clauses_by_status": {
                    "all": all_clauses,
                    "unprocessed": unprocessed_clauses,
                    "in_review": in_review_clauses,
                    "normalised": normalised_clauses,
                    "needs_clarification": needs_clarification_clauses
                }
            }
            
            processed_brds.append(brd_summary)
        
        # Get project details from first BRD
        project_info = {}
        if processed_brds:
            first_brd = processed_brds[0]
            project_info = {
                "project_id": first_brd["project_id"],
                "project_code": first_brd["project_code"],
                "project_name": first_brd["project_name"],
                "customer": first_brd["customer"]
            }
        
        return {
            "message": "BRDs fetched successfully",
            "project_info": project_info,
            "total_brds": total_brds,
            "overall_status_counts": overall_counts,
            "brds": processed_brds
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching normalized BRDs: {str(e)}")


@router.get("/get-brd-clauses-by-status/{brd_id}")
async def get_brd_clauses_by_status(
    brd_id: str,
    status: str = Query(..., description="Status filter: all, unprocessed, in_review, normalised, needs_clarification")
):
    """
    Get BRD clauses filtered by specific status with count.
    
    Status options:
    - all: All clauses
    - unprocessed: Only unprocessed clauses
    - in_review: Only in review clauses
    - normalised: Only normalised clauses
    - needs_clarification: Only needs clarification clauses
    """
    try:
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(brd_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid BRD ID format")
        
        # Fetch BRD
        brd_data = await brd_normalize_collection.find_one({"_id": obj_id})
        
        if not brd_data:
            raise HTTPException(status_code=404, detail="BRD not found")
        
        # Get all clauses
        all_clauses = brd_data.get("clauses", [])
        
        # Status mapping (API parameter to database value)
        status_mapping = {
            "all": None,
            "unprocessed": "Unprocessed",
            "in_review": "In Review",
            "normalised": "Normalised",
            "needs_clarification": "Needs Clarification"
        }
        
        # Validate status parameter
        if status.lower() not in status_mapping:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(status_mapping.keys())}"
            )
        
        # Filter clauses based on status
        if status.lower() == "all":
            filtered_clauses = all_clauses
        else:
            db_status = status_mapping[status.lower()]
            filtered_clauses = [c for c in all_clauses if c.get("status") == db_status]
        
        return {
            "brd_id": brd_id,
            "brd_title": brd_data.get("brd_title"),
            "project_code": brd_data.get("project_code"),
            "project_name": brd_data.get("project_name"),
            "status_filter": status,
            "total_count": len(filtered_clauses),
            "clauses": filtered_clauses
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clauses: {str(e)}")


@router.get("/get-brd-clauses/{brd_id}")
async def get_brd_clauses(
    brd_id: str,
    status: Optional[str] = Query(None, description="Filter by status: Unprocessed, In Review, Normalised, Needs Clarification")
):
    """
    Get all clauses from a BRD, optionally filtered by status
    """
    try:
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(brd_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid BRD ID format")
        
        # Fetch BRD
        brd_data = await brd_normalize_collection.find_one({"_id": obj_id})
        
        if not brd_data:
            raise HTTPException(status_code=404, detail="BRD not found")
        
        clauses = brd_data.get("clauses", [])
        
        # Filter by status if provided
        if status:
            clauses = [c for c in clauses if c.get("status") == status]
        
        return {
            "brd_id": brd_id,
            "brd_title": brd_data.get("brd_title"),
            "total_clauses": len(clauses),
            "status_filter": status,
            "clauses": clauses
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clauses: {str(e)}")


@router.put("/update-clause-status/{brd_id}/{source_ref}")
async def update_clause_status(
    brd_id: str,
    source_ref: str,
    clause_update: ClauseUpdate
):
    """
    Update the status of a specific clause
    
    Example: PUT /api/normalize/update-clause-status/507f1f77bcf86cd799439011/BRD-S3.2.1
    Body: {"status": "Normalised"}
    """
    try:
        # Validate status
        valid_statuses = ["Unprocessed", "In Review", "Normalised", "Needs Clarification"]
        if clause_update.status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(brd_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid BRD ID format")
        
        # Find the BRD
        brd_data = await brd_normalize_collection.find_one({"_id": obj_id})
        
        if not brd_data:
            raise HTTPException(status_code=404, detail="BRD not found")
        
        # Update the specific clause
        clauses = brd_data.get("clauses", [])
        clause_found = False
        
        for clause in clauses:
            if clause.get("source_ref") == source_ref:
                old_status = clause.get("status")
                clause["status"] = clause_update.status
                clause_found = True
                break
        
        if not clause_found:
            raise HTTPException(status_code=404, detail=f"Clause with source_ref '{source_ref}' not found")
        
        # Recalculate status counts
        status_counts = {
            "All": len(clauses),
            "Unprocessed": 0,
            "In Review": 0,
            "Normalised": 0,
            "Needs Clarification": 0
        }
        
        for clause in clauses:
            status = clause.get("status")
            if status in status_counts:
                status_counts[status] += 1
        
        # Update in MongoDB
        result = await brd_normalize_collection.update_one(
            {"_id": obj_id},
            {
                "$set": {
                    "clauses": clauses,
                    "status_counts": status_counts,
                    "updated_at": datetime.now()
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update clause status")
        
        return {
            "message": "Clause status updated successfully",
            "brd_id": brd_id,
            "source_ref": source_ref,
            "old_status": old_status,
            "new_status": clause_update.status,
            "status_counts": status_counts
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating clause status: {str(e)}")


@router.delete("/delete-brd/{brd_id}")
async def delete_brd(brd_id: str):
    """
    Delete a BRD by ID
    """
    try:
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(brd_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid BRD ID format")
        
        # Delete from MongoDB
        result = await brd_normalize_collection.delete_one({"_id": obj_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="BRD not found")
        
        return {
            "message": "BRD deleted successfully",
            "brd_id": brd_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting BRD: {str(e)}")


# ------------------------------
# Normalized Requirements APIs
# ------------------------------

@router.post("/add-normalized-requirement")
async def add_normalized_requirement(requirement: NormalizedRequirement):
    """
    Add a normalized requirement to the database.
    
    Request body example:
    {
        "requirement_title": "Task Creation with Owner, Priority and Due Date",
        "normalised_requirement_statement": "The system shall allow authorized users to create tasks by specifying the owner, priority level and due date.",
        "is_traceable": true,
        "is_testable": true,
        "needs_clarification": false,
        "requirement_type": "Functional",
        "functional_module": "Task Management",
        "actor_user_role": "Task Manager",
        "priority": "High",
        "business_rule": "Task must be assigned to a valid user and due date cannot be in the past.",
        "acceptance_criteria": "Given a user with create permission, when task details are entered, then the task shall be created successfully.",
        "dependencies": "User Management, Calendar Service",
        "owner": "Rohit Sharma (BA)",
        "status": "In Review",
        "source_section": "3.2 Task Management",
        "source_page": 12,
        "source_clause": "BRD-S3.2.1",
        "source_confidence": "92%",
        "brd_id": "6a70c844f7bc4b4a7c24c166",
        "project_id": 1
    }
    """
    try:
        # Auto-generate requirement ID if not provided
        if not requirement.requirement_id:
            # Get count of existing requirements to generate sequential ID
            count = await normalized_requirements_collection.count_documents({})
            requirement.requirement_id = f"NRM-REQ-{str(count + 1).zfill(3)}"
        
        # Prepare document for MongoDB
        requirement_document = {
            "requirement_id": requirement.requirement_id,
            "requirement_title": requirement.requirement_title,
            "normalised_requirement_statement": requirement.normalised_requirement_statement,
            
            # Flags
            "is_traceable": requirement.is_traceable,
            "is_testable": requirement.is_testable,
            "needs_clarification": requirement.needs_clarification,
            
            # Classification
            "requirement_type": requirement.requirement_type,
            "functional_module": requirement.functional_module,
            "actor_user_role": requirement.actor_user_role,
            
            # Details
            "priority": requirement.priority,
            "business_rule": requirement.business_rule,
            "acceptance_criteria": requirement.acceptance_criteria,
            
            # Relationships
            "dependencies": requirement.dependencies,
            "owner": requirement.owner,
            "status": requirement.status,
            
            # Traceability
            "source_section": requirement.source_section,
            "source_page": requirement.source_page,
            "source_clause": requirement.source_clause,
            "source_confidence": requirement.source_confidence,
            
            # Linking
            "brd_id": requirement.brd_id,
            "project_id": requirement.project_id,
            
            # Timestamps
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Insert into MongoDB
        result = await normalized_requirements_collection.insert_one(requirement_document)
        
        return {
            "message": "Normalized requirement added successfully",
            "requirement_id": requirement.requirement_id,
            "requirement_db_id": str(result.inserted_id),
            "requirement_title": requirement.requirement_title
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding normalized requirement: {str(e)}")


@router.get("/get-normalized-requirements-by-project/{project_id}")
async def get_normalized_requirements_by_project(
    project_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return")
):
    """
    Get all normalized requirements for a specific project ID.
    
    Example: GET /api/normalize/get-normalized-requirements-by-project/1
    """
    try:
        # Query for requirements matching this project (handle both int and string IDs)
        query = {"$or": [{"project_id": project_id}, {"project_id": str(project_id)}]}
        
        # Count total requirements
        total = await normalized_requirements_collection.count_documents(query)
        
        if total == 0:
            return {
                "message": f"No normalized requirements found for project ID {project_id}",
                "project_id": project_id,
                "total": 0,
                "requirements": []
            }
        
        # Fetch requirements with pagination
        cursor = normalized_requirements_collection.find(query).skip(skip).limit(limit).sort("created_at", -1)
        requirements = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for req in requirements:
            req["id"] = str(req.pop("_id"))
        
        # Group by status
        status_counts = {
            "Draft": 0,
            "In Review": 0,
            "Ready": 0,
            "Approved": 0
        }
        
        # Group by requirement type
        type_counts = {
            "Functional": 0,
            "Non-Functional": 0,
            "Security": 0,
            "Performance": 0
        }
        
        # Group by priority
        priority_counts = {
            "High": 0,
            "Medium": 0,
            "Low": 0
        }
        
        for req in requirements:
            status = req.get("status", "")
            if status in status_counts:
                status_counts[status] += 1
            
            req_type = req.get("requirement_type", "")
            if req_type in type_counts:
                type_counts[req_type] += 1
            
            priority = req.get("priority", "")
            if priority in priority_counts:
                priority_counts[priority] += 1
        
        return {
            "message": "Normalized requirements fetched successfully",
            "project_id": project_id,
            "total": total,
            "skip": skip,
            "limit": limit,
            "summary": {
                "status_counts": status_counts,
                "type_counts": type_counts,
                "priority_counts": priority_counts
            },
            "requirements": requirements
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching normalized requirements: {str(e)}")


@router.get("/get-clause/{brd_id}/{source_ref}")
async def get_clause_by_source_ref(brd_id: str, source_ref: str):
    """
    Get a specific clause by BRD ID and source_ref.
    
    Example: GET /api/normalize/get-clause/6a70c844f7bc4b4a7c24c166/BRD-005
    """
    try:
        # Convert string ID to ObjectId
        try:
            obj_id = ObjectId(brd_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid BRD ID format")
        
        # Fetch BRD
        brd_data = await brd_normalize_collection.find_one({"_id": obj_id})
        
        if not brd_data:
            raise HTTPException(status_code=404, detail="BRD not found")
        
        # Find the specific clause by source_ref
        clauses = brd_data.get("clauses", [])
        clause = None
        
        for c in clauses:
            if c.get("source_ref") == source_ref:
                clause = c
                break
        
        if not clause:
            raise HTTPException(
                status_code=404,
                detail=f"Clause with source_ref '{source_ref}' not found in BRD. Available source_refs: {[c.get('source_ref') for c in clauses]}"
            )
        
        return {
            "brd_id": brd_id,
            "brd_title": brd_data.get("brd_title"),
            "project_id": brd_data.get("project_id"),
            "project_code": brd_data.get("project_code"),
            "project_name": brd_data.get("project_name"),
            "clause": clause
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clause: {str(e)}")

