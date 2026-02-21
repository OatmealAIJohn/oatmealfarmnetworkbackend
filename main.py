from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://oatmealfarmnewtorkbackend-802455386518.us-central1.run.app",
        "https://your-react-app-url.run.app"  # add your frontend URL here
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}