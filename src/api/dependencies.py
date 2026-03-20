from fastapi import Header, HTTPException
from src.models.company import Company

async def get_current_company(x_api_key: str = Header(...)) -> Company:
    company = Company.objects(
        api_keys__match={"key_hash": x_api_key, "is_active": True}
    ).first()  # type: ignore
    if not company:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return company
