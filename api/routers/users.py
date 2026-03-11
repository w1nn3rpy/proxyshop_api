from fastapi import APIRouter, Depends
from api.app.dependencies import get_api_user

router = APIRouter(prefix="/api")


@router.get(
    "/balance",
    summary="Get account balance",
    description="Returns current balance and proxy prices for the API user"
)
async def get_balance(user=Depends(get_api_user)):

    return {
        "balance": user["balance"],
        "prices": {
            "res": user["res_price"],
            "def": user["def_price"],
            "nondef": user["nondef_price"]
        },
        "status": user["status"]
    }