
from pathlib import Path
import sys
import traceback
import math

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "model"

# The model's internal imports use names such as `config` and
# `candidate_generation`, so add the model directory to Python's path.
sys.path.insert(0, str(MODEL_DIR))

from model.site_optimizer import recommend_sites
from model.config import CandidateParams, OptimizerParams

app = FastAPI(title="SAKLAW API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class CandidateRequest(BaseModel):
    k: int = Field(default=5, ge=1, le=100)
    alternatives: int = Field(default=5, ge=1, le=20)
    alt_separation_km: float = Field(default=5, ge=0)
    use_cache: bool = True
    use_priority_filter: bool = True



def json_safe(value):
    """Convert common Python/numpy values into JSON-safe values."""
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass

    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # Convert objects such as Impact into dictionaries.
    if hasattr(value, "__dict__"):
        return json_safe(vars(value))

    return str(value)



@app.get("/api/health")
def health():
    return {"status": "ok", "service": "saklaw-api"}


@app.post("/api/candidates")
def generate_candidates(request: CandidateRequest):
    try:
        cparams = CandidateParams(
            use_priority_filter=request.use_priority_filter
        )

        oparams = OptimizerParams(
            alternative_separation_m=request.alt_separation_km * 1000
        )

        results, candidates, summary = recommend_sites(
            k=request.k,
            n_alternatives=request.alternatives,
            cparams=cparams,
            oparams=oparams,
            use_cache=request.use_cache,
            verbose=False,
            write=True,
        )

        combinations = []

        for result in results:
            sites = []

            for selected_site in result.selected:
                candidate_id = selected_site["candidate_id"]

                # Look up the authoritative coordinates and other fields
                # in the candidate dataframe.
                matches = candidates.loc[
                    candidates["candidate_id"] == candidate_id
                ]

                if matches.empty:
                    raise ValueError(
                        f"Could not find candidate {candidate_id}"
                    )

                candidate = matches.iloc[0].to_dict()

                sites.append({
                    **json_safe(selected_site),
                    "longitude": json_safe(candidate["longitude"]),
                    "latitude": json_safe(candidate["latitude"]),
                })

            combinations.append({
                "rank": result.combination,
                "sites": sites,
                "baseline": json_safe(result.baseline),
                "final": json_safe(result.final),
                "network_impact": json_safe(
                    vars(result.network_impact)
                ),
                "warnings": json_safe(result.warnings),
                "timings": json_safe(result.timings),
            })

        return {
            "status": "completed",
            "combinations_found": len(combinations),
            "requested_sites_per_combination": request.k,
            "summary": json_safe(summary),
            "combinations": combinations,
        }

    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="SAKLAW model failed. Check the backend terminal.",
        )
