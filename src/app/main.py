from fastapi import FastAPI

app = FastAPI(title="InsightFlow AI - Backend")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
