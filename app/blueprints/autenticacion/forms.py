from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional


class RegistroForm(FlaskForm):
    empresa_nombre = StringField("Empresa", validators=[DataRequired(), Length(max=150)])
    rubro = SelectField(
        "Rubro de la empresa",
        choices=[
            ("general", "Comercio general"),
            ("almacen", "Almacén"),
            ("minimarket", "Minimarket"),
            ("botilleria", "Botillería"),
            ("ferreteria", "Ferretería"),
            ("farmacia", "Farmacia"),
        ],
        default="general",
        validators=[DataRequired()],
    )
    empresa_identificacion_fiscal = StringField(
        "RUT de la empresa", validators=[Optional(), Length(max=30)]
    )
    empresa_telefono = StringField(
        "Teléfono de la empresa", validators=[Optional(), Length(max=30)]
    )
    identificacion_fiscal = StringField(
        "RUT de la persona responsable", validators=[Optional(), Length(max=30)]
    )
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=100)])
    apellido = StringField("Apellido", validators=[Optional(), Length(max=100)])
    telefono = StringField("Teléfono personal", validators=[Optional(), Length(max=30)])
    email = StringField("Correo", validators=[DataRequired(), Email(), Length(max=254)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=12, max=128)])
    confirmar_password = PasswordField(
        "Confirmar contraseña", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Crear cuenta")


class LoginForm(FlaskForm):
    email = StringField("Correo", validators=[DataRequired(), Email(), Length(max=254)])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(max=128)])
    recordar = BooleanField("Recordarme")
    submit = SubmitField("Ingresar")


class SolicitarRestablecimientoForm(FlaskForm):
    email = StringField("Correo", validators=[DataRequired(), Email(), Length(max=254)])
    submit = SubmitField("Enviar instrucciones")


class RestablecerPasswordForm(FlaskForm):
    password = PasswordField(
        "Nueva contraseña", validators=[DataRequired(), Length(min=12, max=128)]
    )
    confirmar_password = PasswordField(
        "Confirmar contraseña", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Cambiar contraseña")
