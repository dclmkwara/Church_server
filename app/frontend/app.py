from fasthtml.common import serve

try:
    from .dclm_admin.app_factory import app
except ImportError:
    from app.frontend.dclm_admin.app_factory import app


if __name__ == "__main__":
    serve()

