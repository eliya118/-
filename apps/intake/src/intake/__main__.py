import uvicorn


def main() -> None:
    uvicorn.run("intake.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
