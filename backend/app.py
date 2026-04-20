"""
ChatKit Demo Backend using OpenAI ChatKit SDK

This backend implements the ChatKit server protocol, providing a chat interface
using the OpenAI ChatKit SDK.
"""

import os
import json
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
import random
import sys
import uuid
import httpx
import logging
from typing import Any, Dict

import uvicorn
from agents import (
    Agent,
    FileSearchTool,
    GuardrailFunctionOutput,
    input_guardrail,
    InputGuardrailTripwireTriggered,
    ModelSettings,
    Runner
)
from openai import AsyncOpenAI
from openai.types.responses.response_output_text import (
    AnnotationContainerFileCitation,
    AnnotationFileCitation,
)
from pydantic import BaseModel
from chatkit.agents import (
    AgentContext,
    ResponseStreamConverter,
    simple_to_agent_input,
    stream_agent_response,
)
from chatkit.server import ChatKitServer, StreamingResult
from chatkit.types import (
  Annotation,
  FileSource,
  ThreadMetadata,
  ThreadStreamEvent,
  UserMessageItem,
  ThreadMetadata,
  UserMessageItem,
  AssistantMessageItem,
  AssistantMessageContent,
  ThreadItemDoneEvent,
  ThreadStreamEvent
)
from openai.types.shared import Reasoning
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from simple_store import SimpleStore

# Load environment variables
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env", override=True)

OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID")

# VECTOR_STORE_ID = "vs_68c3406b54148191b1bccebbc53ee263" # Hitchhikers
VECTOR_STORE_ID = "vs_69e2a4dd47e881919bb0afe1ea9eaa6b" # Samsung

class RelevancyCheck(BaseModel):
    is_relevant: bool
    reasoning: str

guardrail_agent= Agent(
    name="Query Relevance Guard",
    # instructions=(
    #     "Determine if the query is relevant to Yext services, technology product questions, general technology troubleshooting, or the capabilities of the agent. "
    #     "Return is_relevant=False if the query is not related to these topics."
    # ),
    instructions=(
        "Determine if the query is relevant to customer support, technology product questions, general technology troubleshooting, or the capabilities of the agent. "
        "Return is_relevant=False if the query is not related to these topics."
    ),
    output_type=RelevancyCheck
)

@input_guardrail(run_in_parallel=False) # ensures that it finishes before streaming starts
async def relevancy_guard(ctx, agent, input_data):
    result = await Runner.run(guardrail_agent, input_data, context=ctx)
    _log_token_usage("relevancy_guard", result)
    analysis: RelevancyCheck = result.final_output
    print(f"Relevancy check: is_relevant={analysis.is_relevant}, reasoning={analysis.reasoning}")

    return GuardrailFunctionOutput(
        tripwire_triggered=not analysis.is_relevant,
        output_info=analysis.reasoning
    )


rag_agent = Agent(
    name="RAG assistant",
    instructions=(
        "You are a Samsung help center support agent. You help customers with troubleshooting and product recommendations."
        "Only use information from the Knowledge Base. "
        "If no answer is found, say 'I don't know' or similar. "
        "In your response, do not mention the file store directly, just the references themselves. "
        "Make sure to cite sources when you use them. "
        "If the input is blank or just regular conversation, you can just greet/respond to the user in a friendly manner. "
        "Use list formatting when appropriate."
    ),
    tools=[
        FileSearchTool(
            vector_store_ids=[VECTOR_STORE_ID],
            max_num_results=10,
            include_search_results=True,
        )
    ],
    input_guardrails=[relevancy_guard],
    model="gpt-5-nano",
    model_settings=ModelSettings(
        reasoning=Reasoning(
            effort="low"
        )
    )
)

LOG_FORMAT = "%(asctime)s %(message)s"
logging.basicConfig(
    format=LOG_FORMAT,
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
LOGGER = logging.getLogger(__name__)


def _extract_request_id(context: Any) -> str | None:
    current = context
    for _ in range(4):
        if current is None:
            return None
        if isinstance(current, dict):
            request_id = current.get("request_id")
            return request_id if isinstance(request_id, str) else None

        request_context = getattr(current, "request_context", None)
        if isinstance(request_context, dict):
            request_id = request_context.get("request_id")
            if isinstance(request_id, str):
                return request_id

        nested_context = getattr(current, "context", None)
        if nested_context is not None and nested_context is not current:
            current = nested_context
            continue
        if request_context is not None and request_context is not current:
            current = request_context
            continue
        break

    return None


def _log_token_usage(label: str, result: Any) -> None:
    context_wrapper = getattr(result, "context_wrapper", None)
    usage = getattr(context_wrapper, "usage", None)
    request_id = _extract_request_id(getattr(context_wrapper, "context", None))
    request_id_part = f" request_id={request_id}" if request_id else ""

    if usage is None:
        LOGGER.info("---- Token usage [%s]%s unavailable", label, request_id_part)
        return

    request_entries = list(getattr(usage, "request_usage_entries", []))
    if request_entries:
        for index, request_usage in enumerate(request_entries, start=1):
            LOGGER.info(
                "---- Token usage [%s call=%s/%s]%s input=%s output=%s total=%s",
                label,
                index,
                len(request_entries),
                request_id_part,
                request_usage.input_tokens,
                request_usage.output_tokens,
                request_usage.total_tokens,
            )

    LOGGER.info(
        "---- Token usage [%s total]%s input=%s output=%s total=%s requests=%s",
        label,
        request_id_part,
        usage.input_tokens,
        usage.output_tokens,
        usage.total_tokens,
        usage.requests,
    )


class MetadataAwareResponseStreamConverter(ResponseStreamConverter):
    """Populate file citation titles from vector-store file attributes."""

    def __init__(self, client: AsyncOpenAI, vector_store_id: str):
        super().__init__()
        self.client = client
        self.vector_store_id = vector_store_id
        self._file_metadata_cache: dict[
            str, tuple[str | None, str | None, str | None]
        ] = {}

    def _metadata_from_attributes(
        self, attributes: dict[str, Any] | None
    ) -> tuple[str | None, str | None, str | None]:
        attributes = attributes or {}

        title = None
        subtitle = None
        link = None

        name = attributes.get("name")
        if isinstance(name, str) and name.strip():
            title = name.strip()

        price = attributes.get("price")
        if isinstance(price, str) and price.strip():
            subtitle = price.strip()
        elif isinstance(price, (int, float, bool)):
            subtitle = str(price)

        raw_link = attributes.get("link")
        if isinstance(raw_link, str) and raw_link.strip():
            link = raw_link.strip()

        return title, subtitle, link

    def cache_file_search_results(self, results: list[Any] | None) -> None:
        if not results:
            return

        for result in results:
            file_id = getattr(result, "file_id", None)
            if not isinstance(file_id, str) or not file_id:
                continue
            self._file_metadata_cache[file_id] = self._metadata_from_attributes(
                getattr(result, "attributes", None)
            )

    async def _get_file_metadata(
        self, file_id: str, fallback_filename: str
    ) -> tuple[str, str | None, str | None]:
        cached_metadata = self._file_metadata_cache.get(file_id)
        if cached_metadata is not None:
            title, subtitle, link = cached_metadata
            return title or fallback_filename, subtitle, link

        try:
            vector_store_file = await self.client.vector_stores.files.retrieve(
                file_id=file_id,
                vector_store_id=self.vector_store_id,
            )
            metadata = self._metadata_from_attributes(vector_store_file.attributes)
        except Exception:
            LOGGER.warning(
                "Failed to load vector store metadata for citation file %s",
                file_id,
                exc_info=True,
            )
            metadata = (None, None, None)

        self._file_metadata_cache[file_id] = metadata
        title, subtitle, link = metadata
        return title or fallback_filename, subtitle, link

    async def file_citation_to_annotation(
        self, file_citation: AnnotationFileCitation
    ) -> Annotation | None:
        filename = file_citation.filename
        if not filename:
            return None

        title = filename
        subtitle = None
        link = None
        if file_citation.file_id:
            title, subtitle, link = await self._get_file_metadata(
                file_citation.file_id,
                filename,
            )

        return Annotation(
            source=FileSource(
                filename=filename,
                title=title,
                description=subtitle,
                group=link,
            ),
            index=file_citation.index,
        )

    async def container_file_citation_to_annotation(
        self, container_file_citation: AnnotationContainerFileCitation
    ) -> Annotation | None:
        filename = container_file_citation.filename
        if not filename:
            return None

        title = filename
        subtitle = None
        link = None
        if container_file_citation.file_id:
            title, subtitle, link = await self._get_file_metadata(
                container_file_citation.file_id,
                filename,
            )

        return Annotation(
            source=FileSource(
                filename=filename,
                title=title,
                description=subtitle,
                group=link,
            ),
            index=container_file_citation.end_index,
        )


openai_client = (
    AsyncOpenAI(project=OPENAI_PROJECT_ID)
    if OPENAI_PROJECT_ID
    else AsyncOpenAI()
)
response_stream_converter = MetadataAwareResponseStreamConverter(
    client=openai_client,
    vector_store_id=VECTOR_STORE_ID,
)


class MetadataCachingRunResult:
    """Intercept file search tool results so citation metadata can be cached."""

    def __init__(
        self,
        result: Any,
        converter: MetadataAwareResponseStreamConverter,
    ):
        self._result = result
        self._converter = converter

    def __getattr__(self, name: str) -> Any:
        return getattr(self._result, name)

    async def stream_events(self) -> AsyncIterator[Any]:
        async for event in self._result.stream_events():
            if event.type == "raw_response_event":
                raw_event = event.data
                if raw_event.type == "response.output_item.done":
                    item = raw_event.item
                    if getattr(item, "type", None) == "file_search_call":
                        self._converter.cache_file_search_results(
                            getattr(item, "results", None)
                        )
            yield event


class DemoChatKitServer(ChatKitServer[Dict[str, Any]]):
    """ChatKit server implementation."""

    def __init__(self, data_store: SimpleStore):
        # Initialize with no attachment store for simplicity
        super().__init__(data_store, attachment_store=None)


    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Handle incoming user messages and generate responses."""
        # Run the agent *streamed* with full thread history
        agent_ctx = AgentContext(
            thread=thread,
            store=self.store,
            request_context=context,
        )

        items_page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=1000,
            order="asc",
            context=context,
        )
        agent_input = await simple_to_agent_input(items_page.data)

        try:
            result = Runner.run_streamed(rag_agent, agent_input, context=agent_ctx)
            metadata_caching_result = MetadataCachingRunResult(
                result,
                response_stream_converter,
            )

            # IMPORTANT: this converts Responses/Agents streaming events -> ChatKit ThreadStreamEvents
            # and auto-attaches file/url citations as ChatKit annotations (Sources in UI).
            async for ev in stream_agent_response(
                agent_ctx,
                metadata_caching_result,
                converter=response_stream_converter,
            ):
                yield ev
            _log_token_usage("rag_agent", result)
        except InputGuardrailTripwireTriggered as exc:
            output_info = exc.guardrail_result.output.output_info
            # message_text = (
            #     output_info
            #     if isinstance(output_info, str) and output_info.strip()
            #     else "Sorry, this falls outside of the scope I am able to assist with."
            # )
            message_text = "Sorry, this falls outside of the scope I am able to assist with."
            message = AssistantMessageItem(
                id=self.store.generate_item_id("message", thread, context),
                thread_id=thread.id,
                created_at=datetime.now(),
                content=[
                    AssistantMessageContent(
                        text=message_text,
                        annotations=[],
                    )
                ],
            )
            yield ThreadItemDoneEvent(item=message)




# Create FastAPI app
app = FastAPI(title="ChatKit Demo Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create store and server
data_store = SimpleStore()
chatkit_server = DemoChatKitServer(data_store)


@app.post("/chatkit")
async def chatkit_endpoint(request: Request):
    body = await request.body()
    request_id = str(uuid.uuid4())
    context = {"request_id": request_id}

    LOGGER.info("Processing /chatkit request_id=%s", request_id)
    print("threads: ", chatkit_server.store.threads)
    result = await chatkit_server.process(body, context)

    # STREAMING (SSE)
    if  isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")

    # NON-STREAMING
    else:
        return Response(content=result.json, media_type="application/json")


# @app.post("/chatkit/session")
# async def chatkit_session():
#     session = chatkit_server.create_session(
#         # 👇 THIS is the critical part
#         api_url="https://your-python-api.example.com/chatkit"
#     )

#     return {
#         "client_secret": session.client_secret
#     }


# @app.post("/api/chatkit_session")
# async def create_chatkit_session(request: Request):
#     # Optional: get the frontend's allowed origin
#     origin = request.headers.get("origin")
#     cors_headers = {"Access-Control-Allow-Origin": origin or "*"}

#     try:
#         payload = await request.json()
#     except Exception:
#         return JSONResponse(
#             status_code=400,
#             content={"message": "Invalid JSON body"},
#             headers=cors_headers,
#         )
#     workflow_id = payload.get("workflowId") or payload.get("workflow_id")
#     if not workflow_id:
#         return JSONResponse(
#             status_code=400,
#             content={"message": "Missing workflowId"},
#             headers=cors_headers,
#         )

#     # Optionally, associate the session with a user ID
#     user_id = str(uuid.uuid4())
#     openai_api_key = os.getenv("OPENAI_API_KEY")
#     if not openai_api_key:
#         return JSONResponse(
#             status_code=500,
#             content={"message": "Missing OPENAI_API_KEY"},
#             headers=cors_headers,
#         )

#     url = "https://api.openai.com/v1/chatkit/sessions"
#     session_payload = {
#         "workflow": {"id": workflow_id},
#         "user": user_id,
#         "chatkit_configuration": { "file_upload": { "enabled": True } }
#     }

#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             upstream_response = await client.post(
#                 url,
#                 headers={
#                     "Content-Type": "application/json",
#                     "Authorization": f"Bearer {openai_api_key}",
#                     "OpenAI-Beta": "chatkit_beta=v1",
#                 },
#                 json=session_payload,
#             )
#     except httpx.HTTPError as exc:
#         LOGGER.exception("Failed to create ChatKit session")
#         return JSONResponse(
#             status_code=502,
#             content={"message": "Failed to reach ChatKit API", "details": str(exc)},
#             headers=cors_headers,
#         )

#     upstream_json = upstream_response.json()
#     if upstream_response.is_error:
#         return JSONResponse(
#             status_code=upstream_response.status_code,
#             content={"message": "Failed to create session", "details": upstream_json},
#             headers=cors_headers,
#         )

#     client_secret = upstream_json.get("client_secret")
#     return JSONResponse(
#         status_code=200,
#         content={"clientSecret": client_secret},
#         headers=cors_headers,
#     )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    
    print("=" * 60)
    print("🚀 ChatKit Server Starting")
    print("=" * 60)
    print(f"📍 Server: http://localhost:{port}")
    print(f"📡 ChatKit endpoint: http://localhost:{port}/chatkit")
    print(f"🔑 API Key configured: {bool(os.getenv('OPENAI_API_KEY'))}")
    print(f"📁 OpenAI project: {OPENAI_PROJECT_ID or '(default)'}")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=port)
