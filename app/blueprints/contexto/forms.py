from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired


class ContextoForm(FlaskForm):
    sucursal_id = SelectField("Sucursal", coerce=int, validators=[DataRequired()])
    bodega_id = SelectField("Bodega", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Usar ubicación")
