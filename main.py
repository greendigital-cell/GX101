from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.brd import router as project_sites_router
from api.auth import router as auth_router
from api.penpot import router as penpot_router
from api.normalize import router as normalize_router
from api.requirement import router as requirement_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(project_sites_router, prefix="/api/project-sites", tags=["project-sites"])
app.include_router(penpot_router, prefix="/api/project-sites", tags=["penpot"])
app.include_router(normalize_router, prefix="/api/normalize", tags=["normalize"])
app.include_router(requirement_router, prefix="/api/requirements", tags=["requirements"])

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", port=8001, reload=True)
