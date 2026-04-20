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
    Runner
)
from pydantic import BaseModel
from chatkit.agents import AgentContext, simple_to_agent_input, stream_agent_response
from chatkit.server import ChatKitServer, StreamingResult
from chatkit.types import (
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
            max_num_results=8,
        )
    ],
    input_guardrails=[relevancy_guard],
    # model="gpt-5-nano"
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

            # IMPORTANT: this converts Responses/Agents streaming events -> ChatKit ThreadStreamEvents
            # and auto-attaches file/url citations as ChatKit annotations (Sources in UI).
            async for ev in stream_agent_response(agent_ctx, result):
                yield ev
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
    context = {}

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
