"""Global error handler for the FastAPI application."""

import traceback
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class CVParsingError(Exception):
    """Raised when CV parsing fails."""
    pass


class HallucinationDetectedError(Exception):
    """Raised when Agent 6 attempts to add content not in the original CV."""
    pass


class PipelineError(Exception):
    """Raised when the agent pipeline encounters an error."""
    pass


class AgentError(Exception):
    """Raised when an individual agent fails."""
    pass


def register_error_handlers(app: FastAPI):
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(CVParsingError)
    async def cv_parsing_error_handler(request: Request, exc: CVParsingError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "error_type": "cv_parsing_error"},
        )

    @app.exception_handler(HallucinationDetectedError)
    async def hallucination_error_handler(request: Request, exc: HallucinationDetectedError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc), "error_type": "hallucination_detected"},
        )

    @app.exception_handler(PipelineError)
    async def pipeline_error_handler(request: Request, exc: PipelineError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "error_type": "pipeline_error"},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        traceback.print_exc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred. Please try again.",
                "error_type": "internal_error",
            },
        )
