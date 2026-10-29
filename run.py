import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting Crowdfunding AI Backend server on http://localhost:{port}")
    print(f"📖 Interactive Swagger API Docs: http://localhost:{port}/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
