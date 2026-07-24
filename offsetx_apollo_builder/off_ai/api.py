from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .service import OffAIService


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectCreate(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    instructions: str = Field(default="", max_length=30000)


class ProjectUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    instructions: str | None = Field(default=None, max_length=30000)
    archived: bool | None = None


class ConversationCreate(StrictModel):
    title: str = Field(default="New chat", max_length=160)
    project_id: str = Field(default="", max_length=100)
    selected_profile_id: str = Field(default="", max_length=100)
    task_type: Literal["public_general"] = "public_general"


class ConversationUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    project_id: str | None = Field(default=None, max_length=100)
    selected_profile_id: str | None = Field(default=None, max_length=100)
    task_type: Literal["public_general"] | None = None
    pinned: bool | None = None
    archived: bool | None = None


class MessageCreate(StrictModel):
    prompt: str = Field(min_length=1, max_length=30000)
    selected_profile_id: str = Field(default="", max_length=100)
    task_type: Literal["public_general"] = "public_general"
    allow_failover: bool = True


class MessageRetry(StrictModel):
    assistant_message_id: str = Field(min_length=1, max_length=100)
    selected_profile_id: str = Field(default="", max_length=100)


class IntakeMode(StrictModel):
    mode: Literal["generate", "parse_send"]


class IntakeCommit(StrictModel):
    campaign_name: str = Field(min_length=1, max_length=160)
    daily_send_limit: int = Field(default=20, ge=1, le=20)
    selected_mode: Literal["generate", "parse_send"] | Literal[""] = ""
    selected_profile_id: str = Field(default="", max_length=100)


class TemplateRewrite(StrictModel):
    template_id: str = Field(min_length=1, max_length=100)
    variant_id: str = Field(min_length=1, max_length=80)
    current_template: str = Field(min_length=1, max_length=30000)
    sample_size: int = Field(ge=20, le=10_000_000)
    reply_rate: float = Field(ge=0, le=100)
    selected_profile_id: str = Field(min_length=1, max_length=100)


class RecommendationReview(StrictModel):
    approved: bool


class ToolRegister(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    repository_url: str = Field(min_length=1, max_length=500)
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    image: str = Field(min_length=1, max_length=300)
    command: list[str] = Field(min_length=1, max_length=40)


class ToolExecute(StrictModel):
    public_input: str = Field(default="", max_length=100000)
    timeout_seconds: int = Field(default=60, ge=1, le=120)


def _service(request: Request) -> OffAIService:
    return request.app.state.off_ai


def build_off_ai_router(*, max_upload_bytes: int) -> APIRouter:
    router = APIRouter(prefix="/api/v1/ai", tags=["OFF_AI Studio"])

    @router.get("/bootstrap")
    def bootstrap(request: Request) -> dict[str, Any]:
        return _service(request).bootstrap()

    @router.get("/projects")
    def projects(
        request: Request, include_archived: bool = Query(False)
    ) -> dict[str, Any]:
        items = _service(request).store.list_projects(
            include_archived=include_archived
        )
        return {"items": items, "total": len(items)}

    @router.post("/projects", status_code=201)
    def create_project(body: ProjectCreate, request: Request) -> dict[str, Any]:
        return _service(request).create_project(**body.model_dump())

    @router.patch("/projects/{project_id}")
    def update_project(
        project_id: str, body: ProjectUpdate, request: Request
    ) -> dict[str, Any]:
        return _service(request).store.update_project(
            project_id, body.model_dump(exclude_none=True)
        )

    @router.get("/projects/{project_id}/export")
    def export_project(
        project_id: str,
        request: Request,
        format: Literal["md", "html"] = Query("md"),
    ) -> FileResponse:
        path = _service(request).export_project(project_id, format=format)
        return FileResponse(path, filename=path.name)

    @router.get("/conversations")
    def conversations(
        request: Request,
        project_id: str = Query("", max_length=100),
        search: str = Query("", max_length=300),
        include_archived: bool = Query(False),
        limit: int = Query(200, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _service(request).store.list_conversations(
            project_id=project_id,
            search=search,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @router.post("/conversations", status_code=201)
    def create_conversation(
        body: ConversationCreate, request: Request
    ) -> dict[str, Any]:
        return _service(request).create_conversation(**body.model_dump())

    @router.get("/conversations/{conversation_id}")
    def conversation(conversation_id: str, request: Request) -> dict[str, Any]:
        return _service(request).store.get_conversation(conversation_id)

    @router.patch("/conversations/{conversation_id}")
    def update_conversation(
        conversation_id: str, body: ConversationUpdate, request: Request
    ) -> dict[str, Any]:
        values = body.model_dump(exclude_none=True)
        if "task_type" in values:
            values["data_class"] = _service(request).broker.policy.rule(
                str(values["task_type"])
            ).data_class
        return _service(request).store.update_conversation(
            conversation_id, values
        )

    @router.get("/conversations/{conversation_id}/messages")
    def messages(
        conversation_id: str,
        request: Request,
        limit: int = Query(500, ge=1, le=1000),
        before: str = Query("", max_length=80),
    ) -> dict[str, Any]:
        items = _service(request).store.list_messages(
            conversation_id, limit=limit, before=before
        )
        return {"items": items, "total": len(items)}

    @router.post("/conversations/{conversation_id}/messages", status_code=201)
    def send_message(
        conversation_id: str, body: MessageCreate, request: Request
    ) -> dict[str, Any]:
        return _service(request).send_message(
            conversation_id=conversation_id, **body.model_dump()
        )

    @router.post("/conversations/{conversation_id}/retry", status_code=201)
    def retry_message(
        conversation_id: str, body: MessageRetry, request: Request
    ) -> dict[str, Any]:
        return _service(request).retry_message(
            conversation_id=conversation_id, **body.model_dump()
        )

    @router.get("/conversations/{conversation_id}/context")
    def context(conversation_id: str, request: Request) -> dict[str, Any]:
        _service(request).store.get_conversation(conversation_id)
        return _service(request).store.get_context(
            "conversation", conversation_id, create=True
        )

    @router.post("/intakes/inspect", status_code=201)
    async def inspect_intake(
        request: Request,
        file: UploadFile = File(...),
        conversation_id: str = Form(""),
        template_text: str = Form(""),
        public_positioning: str = Form(""),
        selected_mode: str = Form(""),
    ) -> dict[str, Any]:
        filename = file.filename or "upload"
        content = await file.read(max_upload_bytes + 1)
        if len(content) > max_upload_bytes:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=413, detail="Campaign intake file exceeds the upload limit"
            )
        return _service(request).inspect_intake(
            conversation_id=conversation_id,
            filename=filename,
            media_type=file.content_type or "application/octet-stream",
            content=content,
            template_text=template_text,
            public_positioning=public_positioning,
            selected_mode=selected_mode,
        )

    @router.get("/intakes/{job_id}")
    def intake(job_id: str, request: Request) -> dict[str, Any]:
        return _service(request).store.get_import_job(job_id)

    @router.post("/intakes/{job_id}/mode")
    def choose_intake_mode(
        job_id: str, body: IntakeMode, request: Request
    ) -> dict[str, Any]:
        return _service(request).choose_intake_mode(job_id, body.mode)

    @router.post("/intakes/{job_id}/commit")
    def commit_intake(
        job_id: str, body: IntakeCommit, request: Request
    ) -> dict[str, Any]:
        return _service(request).commit_intake(
            job_id=job_id, **body.model_dump()
        )

    @router.get("/egress")
    def egress_calls(
        request: Request,
        status: str = Query("", max_length=30),
        profile_id: str = Query("", max_length=100),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _service(request).store.list_egress(
            status=status, profile_id=profile_id, limit=limit, offset=offset
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @router.get("/egress/{call_id}")
    def egress_call(call_id: str, request: Request) -> dict[str, Any]:
        return _service(request).store.get_egress(call_id)

    @router.get("/owner-record/export")
    def owner_record_export(
        request: Request, format: Literal["md", "json"] = Query("md")
    ) -> FileResponse:
        path = _service(request).export_owner_record(format=format)
        return FileResponse(path, filename=path.name)

    @router.get("/tools")
    def tools(request: Request) -> dict[str, Any]:
        items = _service(request).tools.list()
        return {"items": items, "total": len(items)}

    @router.post("/tools", status_code=201)
    def register_tool(body: ToolRegister, request: Request) -> dict[str, Any]:
        return _service(request).tools.register(**body.model_dump())

    @router.post("/tools/{tool_id}/prepare")
    def prepare_tool(tool_id: str, request: Request) -> dict[str, Any]:
        return _service(request).tools.prepare(tool_id)

    @router.post("/tools/{tool_id}/execute")
    def execute_tool(
        tool_id: str, body: ToolExecute, request: Request
    ) -> dict[str, Any]:
        return _service(request).tools.execute(tool_id, **body.model_dump())

    @router.post("/template-recommendations", status_code=201)
    def template_recommendation(
        body: TemplateRewrite, request: Request
    ) -> dict[str, Any]:
        return _service(request).suggest_template_rewrite(**body.model_dump())

    @router.get("/template-recommendations")
    def template_recommendations(
        request: Request,
        status: str = Query("", max_length=40),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _service(request).store.list_template_recommendations(
            status=status, limit=limit, offset=offset
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @router.patch("/template-recommendations/{recommendation_id}")
    def review_template_recommendation(
        recommendation_id: str,
        body: RecommendationReview,
        request: Request,
    ) -> dict[str, Any]:
        return _service(request).review_template_recommendation(
            recommendation_id, approved=body.approved
        )

    return router
