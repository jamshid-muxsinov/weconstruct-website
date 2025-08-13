from starlette_wtf import StarletteForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional as Opt

class GeneralQuoteForm(StarletteForm):
    name = StringField(
        'Ваше имя',
        validators=[DataRequired(message="Пожалуйста, укажите ваше имя.")],
        render_kw={"placeholder": " "}
    )
    phone = StringField(
        'Ваш телефон',
        validators=[
            DataRequired(message="Пожалуйста, укажите ваш телефон."),
            Length(min=9, message="Номер телефона кажется слишком коротким.")
        ],
        render_kw={"placeholder": " ", "type": "tel"}
    )
    message = TextAreaField(
        'Ваше сообщение (необязательно)',
        validators=[Opt(), Length(max=2000)],
        render_kw={"placeholder": " ", "rows": 4}
    )

class QuoteForm(StarletteForm):
    name = StringField(
        'Ваше имя *',
        validators=[DataRequired(message="Пожалуйста, укажите ваше имя.")],
        render_kw={"placeholder": " "}
    )
    phone = StringField(
        'Ваш телефон *',
        validators=[
            DataRequired(message="Пожалуйста, укажите ваш телефон."),
            Length(min=9, message="Номер телефона кажется слишком коротким.")
        ],
        render_kw={"placeholder": " ", "type": "tel"}
    )
    message = TextAreaField('Комментарий', validators=[Opt()])