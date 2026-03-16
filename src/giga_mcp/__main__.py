from .server import app


def main():
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
