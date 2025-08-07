from fastapi import FastAPI
from fastapi.responses import FileResponse
from repo_worker import get_filepath, get_metadata

from helper_classes import ComicInfo

app = FastAPI(title="Comic Server")


@app.get("/comics/{comic_id}")
def get_comic_metadata(comic_id: str) -> ComicInfo:
    return get_metadata(comic_id=comic_id)


@app.get("/comics/{comic_id}/download")
def download_comic(comic_id: str):
    return FileResponse(get_filepath(comic_id), media_type="application/zip")
