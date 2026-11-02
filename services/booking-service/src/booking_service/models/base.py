from sqlmodel import SQLModel
from sqlalchemy.orm import registry

class Model(SQLModel,registry=registry()):
    pass
