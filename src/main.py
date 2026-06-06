import uvicorn

from src.api.main import app
from src.core.logging import logger
from src.scheduler.jobs import start_scheduler, stop_scheduler





if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)