from starlette_wtf import StarletteForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional as Opt, Regexp

PHONE_REGEX = r'^\+?[0-9\s()-]+$'
PHONE_ERROR_MESSAGE = "Номер телефона может содержать только цифры, +, -, скобки и пробелы."
PHONE_TITLE_MESSAGE = "Допустимые символы: 0-9, +, -, (), пробел."

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
            Regexp(regex=PHONE_REGEX, message=PHONE_ERROR_MESSAGE)
        ],
        render_kw={
            "placeholder": " ", 
            "type": "tel",
            "pattern": PHONE_REGEX,    
            "title": PHONE_TITLE_MESSAGE 
        }
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
            Regexp(regex=PHONE_REGEX, message=PHONE_ERROR_MESSAGE)
        ],
        render_kw={
            "placeholder": " ", 
            "type": "tel",
            "pattern": PHONE_REGEX,     
            "title": PHONE_TITLE_MESSAGE  
        }
    )
    message = TextAreaField('Комментарий', validators=[Opt()])