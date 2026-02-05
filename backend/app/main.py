from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import upload, extract, hospitals, compare

app = FastAPI(
    title="BillCheck API",
    description="Hospital bill sanity checker powered by CMS price transparency data",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(extract.router, prefix="/api", tags=["extract"])
app.include_router(hospitals.router, prefix="/api", tags=["hospitals"])
app.include_router(compare.router, prefix="/api", tags=["compare"])

@app.get("/")
async def root():
    return {
        "message": "BillCheck API",
        "version": "0.1.0",
        "status": "running",
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
