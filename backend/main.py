from fastapi import FastAPI

app = FastAPI(
    title="Pollux",
    description="Cash Flow Statement Extraction API",
    version="0.1.0",
)


@app.get("/")
def root():
    return {
        "name": "Pollux",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }