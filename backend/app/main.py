from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .routers import admin, evaluation, auth, companies, company_profile, documents, reports, review, strategy, surveys, survey_links, use_cases

app = FastAPI(title="Ruta IA")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(survey_links.router)
app.include_router(company_profile.router)
app.include_router(documents.router)
app.include_router(surveys.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(evaluation.router)
app.include_router(strategy.router)
app.include_router(use_cases.router)
app.include_router(review.router)


@app.get("/health")
def health():
    return {"ok": True}
