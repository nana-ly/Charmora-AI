from fastapi import FastAPI


app = FastAPI(title="ShopGuide RAG API")


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "ShopGuide RAG API",
        "status": "running",
    }


@app.get("/health")
def read_health() -> dict[str, str]:
    return {"status": "ok"}
