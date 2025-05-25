from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, text # Importar 'text'
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy_utils import database_exists, create_database
import os
import time

app = FastAPI()

# Configuración de la base de datos
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://user:password@db/mydatabase")

# Intentar conectar a la base de datos con reintentos
max_retries = 10
retry_delay = 5  # segundos

engine = None # Inicializar engine fuera del bucle
for i in range(max_retries):
    try:
        engine = create_engine(DATABASE_URL)
        # Verificar si la base de datos existe, si no, crearla
        if not database_exists(engine.url):
            create_database(engine.url)
        # Intentar conectar para verificar que la DB esté lista
        with engine.connect() as connection:
            print(f"Conexión a la base de datos exitosa después de {i+1} intentos.")
        break
    except Exception as e:
        print(f"Intento {i+1}/{max_retries}: Falló la conexión a la base de datos: {e}")
        time.sleep(retry_delay)
else:
    raise Exception("No se pudo conectar a la base de datos después de múltiples intentos.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Definición del modelo de la base de datos
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)

# Crear tablas (si no existen)
Base.metadata.create_all(bind=engine)

# Dependencia para obtener la sesión de la base de datos
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    # Insertar algunos datos de ejemplo si la tabla está vacía
    db = SessionLocal()
    try:
        if db.query(Item).count() == 0:
            print("Insertando datos de ejemplo en la base de datos.")
            db.add(Item(name="Elemento de Prueba 1"))
            db.add(Item(name="Elemento de Prueba 2"))
            db.commit()
            print("Datos de ejemplo insertados.")
    except Exception as e:
        print(f"Error al insertar datos de ejemplo: {e}")
        db.rollback()
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "¡Hola desde FastAPI!"}

@app.get("/items/")
async def read_items(db: Session = Depends(get_db)):
    try:
        item = db.query(Item).first()
        # Obtener la versión de MySQL
        mysql_version_row = db.execute(text("SELECT VERSION();")).fetchone()
        mysql_version = mysql_version_row[0] if mysql_version_row else "Desconocida"

        if item:
            return {
                "message": "Datos obtenidos con éxito",
                "db_item_id": item.id,
                "db_item_name": item.name,
                "mysql_version": mysql_version # <--- Añadimos la versión de MySQL
            }
        else:
            return {
                "message": "No hay elementos en la base de datos, ¡pero el backend funciona!",
                "db_item_id": None,
                "db_item_name": None,
                "mysql_version": mysql_version # <--- Añadimos la versión de MySQL
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer datos de la base de datos o obtener versión: {e}")

# Nueva ruta para obtener solo la versión de MySQL
@app.get("/version/")
async def get_mysql_version(db: Session = Depends(get_db)):
    try:
        mysql_version_row = db.execute(text("SELECT VERSION();")).fetchone()
        mysql_version = mysql_version_row[0] if mysql_version_row else "Desconocida"
        return {"mysql_version": mysql_version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener la versión de MySQL: {e}")