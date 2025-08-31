from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, create_engine

import api.repo_worker as repo_worker
from database.gui_repo_worker import RepoWorker

app = FastAPI(title="Comic Server")

engine = create_engine("sqlite:///comics.db")


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/library")
def get_library():
    return repo_worker.get_base_folders("D:/adams-comics")


@app.get("/folder/{folder_name}")
def get_folder_contents(folder_name: str):
    with Session(engine) as session:
        mapping = repo_worker.get_file_to_id_mapping(session, int(folder_name[0]))
    folder_structure = repo_worker.build_tree(folder_name, mapping)
    return folder_structure


@app.get("/cover/{file_id}")
def get_cover_image(comic_id: str):
    cover_base = "D:/adams-comics/.covers/"
    filename = f"{comic_id}_t.jpg"
    cover_path = cover_base + filename
    return FileResponse(cover_path, media_type="image/jpeg")


@app.get("/comics/{comic_id}/metadata")
def get_metadata(comic_id: str):
    with RepoWorker("D:/adams-comics/.covers") as worker:
        return worker.get_complete_metadata(comic_id).model_dump()


@app.get("/comics/{comic_id}/download")
def download_comic(comic_id: str):
    path = f"./comics{comic_id}.cbz"

    def iterfile():
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={comic_id}.cbz"},
    )
