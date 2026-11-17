from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import ResourceNotFoundError
from app.middlewares.request_context import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    register_exception_handlers,
)


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/missing")
    def missing():
        raise ResourceNotFoundError("Nothing here.")

    @app.get("/crash")
    def crash():
        raise RuntimeError("boom")

    return app


def test_request_id_is_generated_and_echoed():
    client = TestClient(build_app())

    generated = client.get("/ok")
    echoed = client.get("/ok", headers={REQUEST_ID_HEADER: "abc"})

    assert generated.headers[REQUEST_ID_HEADER]
    assert echoed.headers[REQUEST_ID_HEADER] == "abc"


def test_domain_not_found_maps_to_404():
    client = TestClient(build_app())

    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Nothing here."


def test_unhandled_error_returns_json_500():
    client = TestClient(build_app(), raise_server_exceptions=False)

    response = client.get("/crash")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error."
    assert response.json()["request_id"]
