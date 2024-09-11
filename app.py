from fastapi import FastAPI
from typing import Dict


app = FastAPI()

@app.get("/{name}/")
async def greet(name: str) -> Dict[str, str]:
    return {"message": f"Hello {name}!"}