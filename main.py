"""RefGuard API server entry (uvicorn)."""
import uvicorn
from refguard.api import create_app
from refguard.core import settings

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.environment == "development"),
    )
