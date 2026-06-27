from api.models import Base
from api.db import engine

Base.metadata.create_all(bind=engine)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from api.routes import agent
from api.routes.dashboard import router as dashboard_router
from api.routes.driver import router as driver_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(agent.router)
app.include_router(dashboard_router)
app.include_router(driver_router)

@app.get("/")
def home():
    return {
        "message": "SwiftValet Backend Running"
    }

@app.post("/whatsapp-test")
async def whatsapp_test(request: Request):
    data = await request.json()

    print("TEST DATA:", data)

    if data.get("body", "").lower().strip() == "reset":
        return {
            "reply": "Flow reset successfully. Please send car image."
        }

    return {
        "reply": "Test message received."
    }