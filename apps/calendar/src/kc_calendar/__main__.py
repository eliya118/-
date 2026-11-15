import uvicorn


def main() -> None:
    uvicorn.run("kc_calendar.main:app", host="0.0.0.0", port=8000, factory=False)


if __name__ == "__main__":
    main()
