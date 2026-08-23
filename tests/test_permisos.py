from types import SimpleNamespace

from app.permisos import evaluar_permiso


class EmpresaActiva:
    def __init__(self, funciones):
        plan = SimpleNamespace(tiene_funcion=lambda codigo: funciones.get(codigo, False))
        self.suscripcion_actual = SimpleNamespace(plan=plan)

    def esta_activa(self):
        return True


def usuario(rol="empleado", empresa_id=1, funciones=None, especiales=None):
    return SimpleNamespace(
        is_authenticated=True,
        is_active=True,
        rol=rol,
        empresa_id=empresa_id,
        empresa=EmpresaActiva(funciones or {}),
        permisos_especiales=especiales or {},
    )


def test_rechaza_acceso_entre_empresas():
    decision = evaluar_permiso(usuario(), "productos.ver", empresa_id=2)
    assert not decision.permitido
    assert decision.codigo == "empresa_invalida"


def test_permiso_especial_no_salta_plan():
    u = usuario("empleado", especiales={"api.gestionar": True})
    decision = evaluar_permiso(u, "api.gestionar")
    assert not decision.permitido
    assert decision.codigo == "plan_insuficiente"


def test_super_admin_no_opera_empresa():
    u = usuario("super_admin", empresa_id=None)
    assert not evaluar_permiso(u, "productos.editar").permitido
    assert evaluar_permiso(u, "superadmin.empresas").permitido
