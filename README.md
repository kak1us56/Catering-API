# Catering API

## Installation
You can run the project on your machine following next steps 
- Ensure that you have installed docker on your machine
- Create a local `.env` file
    - Copy the default file:
    ```bash
    cp .env.default .env
    ```
    - Open `.env` in your editor and adjust values as needed
- Build and start the containers:
```bash
    docker compose build && docker compose up -d
```
- The project will be available at http://localhost:8000

## Stop the project
To stop the containers, run:
```bash
    docker compose down
```