import pytest

from app import crear_aplicacion
from app.models import PlanSaaS, db


@pytest.fixture
def app():
    app = crear_aplicacion("pruebas")
    with app.app_context():
        db.create_all()
        db.session.add(
            PlanSaaS(
                codigo="prueba",
                nombre="Prueba",
                dias_prueba=30,
                precio_mensual=0,
                precio_anual=0,
                limite_productos=100,
                limite_usuarios=2,
                limite_movimientos_mes=500,
                limite_sucursales=1,
                limite_bodegas=1,
                funciones={"productos": True},
            )
        )
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
