from fastapi import FastAPI
from interfaces.api.example_router import router

app = FastAPI()

app.include_router(router)