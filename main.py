from fastapi import FastAPI
from routes.route import routes  # import the router

app = FastAPI()

app.include_router(routes)