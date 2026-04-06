from __future__ import annotations

import uvicorn

from dealwatch.api.app import create_app
from dealwatch.infra.config import set_log_context, settings


app = create_app()


def main() -> None:
    set_log_context(service_name="api", correlation_id="server-main")
    uvicorn.run(
        "dealwatch.server:app",
        host=settings.API_HOST,
        port=settings.PORT or settings.API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
