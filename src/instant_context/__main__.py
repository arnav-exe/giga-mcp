from .logging import init_logger
from .server import app


def main() -> None:
    init_logger()
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
