from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse
from app.models.imports import DouyinImportRequest, ImportJob
from app.services.douyin_urls import ImportFailure

router = APIRouter(prefix='/api/imports', tags=['URL imports'])


@router.post('/douyin', response_model=ImportJob, status_code=202)
def start_import(body: DouyinImportRequest, request: Request):
    try: return request.app.state.imports.start(body)
    except ImportFailure as exc:
        return JSONResponse({'detail': exc.message, 'error_code': exc.code, 'operation': 'validate_url'}, status_code=422)


@router.get('', response_model=list[ImportJob])
def list_imports(request: Request):
    return request.app.state.repository.list_imports()


@router.get('/{job_id}', response_model=ImportJob)
def get_import(job_id: UUID, request: Request):
    return request.app.state.imports.get(job_id)


@router.post('/{job_id}/cancel', response_model=ImportJob)
def cancel_import(job_id: UUID, request: Request):
    return request.app.state.imports.cancel(job_id)
