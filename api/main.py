from fastapi import FastAPI, Request
from api.routes import agent

app = FastAPI()

app.include_router(agent.router)


@app.get("/")
def home():
    return {"message": "SwiftValet Backend Running"}


@app.post("/whatsapp-test")
async def whatsapp_test(request: Request):
    data = await request.json()
    print("TEST DATA:", data)

    if data.get("body", "").lower().strip() == "reset":
        return {"reply": "Flow reset successfully. Please send car image."}

    return {"reply": "Test message received."}