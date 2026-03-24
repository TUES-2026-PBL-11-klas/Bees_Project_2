from pydantic import BaseModel

class RouteCalculationSchema(BaseModel):
    company_id: str
    vessel_id: str
    start_node_id: str
    end_node_id: str
    optimization_mode: str
