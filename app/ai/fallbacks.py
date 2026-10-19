"""Safe hand-written answers, used only when every model failed the quality guard.

A short calm text is always better than garbage on the screen. `safe_payload(schema, lang)` fills any AI schema
from these phrases by field name, so new schemas work without extra code (unknown text fields get the generic
body sentence).
"""
from typing import Literal, get_args, get_origin

from pydantic import BaseModel

T = {
    "ka": {
        "overview": "შენი რუკა წონასწორობასა და შინაგან ძალაზე მიუთითებს.",
        "ascendant": "ლაგნა გვიჩვენებს, როგორ გხედავს სამყარო: მშვიდს და თავდაჯერებულს.",
        "moon": "მთვარე შენს გრძნობებზე მეტყველებს: ღრმა ხარ და სხვებს კარგად გრძნობ.",
        "sun": "მზე შენი არსია: გაქვს ნება და მიზნისკენ სწრაფვა.",
        "navamsa": "ნავამშა ურთიერთობებში ერთგულებასა და მთლიან ბუნებაზე მიუთითებს.",
        "dasha": "ახლანდელი დაშა მოთმინებისა და ნელი, მაგრამ მყარი ზრდის დროა.",
        "title": "ცის მშვიდი გზავნილი",
        "body": "დღეს ვარსკვლავები მშვიდ და სუფთა ენერგიას გიგზავნიან. ნუ იჩქარებ, მოუსმინე საკუთარ თავს და პატარა ნაბიჯებით იმოქმედე.",
        "advice": "გააკეთე დღეს ერთი პატარა საქმე, რომელსაც დიდი ხანია აჭიანურებ.",
        "word": "სიმშვიდე", "lucky_color": "ოქროსფერი",
        "keywords": ["სიმშვიდე", "ინტუიცია", "მოთმინება"], "challenges": ["აჩქარება", "ეჭვი"],
        "quote": "რაც შენია, თავის დროზე შენამდე მოვა.", "affirmation": "მე ვენდობი საკუთარ გზას.",
        "purpose": "შენი გზაა ისწავლო და სხვებსაც გაუზიარო ის, რაც იცი.",
        "love": "სიყვარულში მთავარია გულწრფელობა და ყურადღება წვრილმანებზე.",
        "career": "საქმეში წარმატებას მოთმინება და თანმიმდევრობა მოგიტანს.",
        "intention": "დღეს ჩაიფიქრე ერთი სურვილი და მკაფიოდ ჩამოაყალიბე.",
        "steps": ["აანთე სანთელი და რამდენჯერმე ღრმად ჩაისუნთქე.", "ფურცელზე დაწერე შენი სურვილი.",
                  "ფურცელი შეინახე შემდეგ სავსე მთვარემდე."],
        "avoid": "მოერიდე აჩქარებულ გადაწყვეტილებებს.",
        "answer": "ვარსკვლავები ახლა ბინდში არიან, ამიტომ მოკლედ გიპასუხებ: ენდე ინტუიციას და ნაბიჯ-ნაბიჯ იმოქმედე. "
                  "ცოტა ხანში ისევ მკითხე.",
        "follow_ups": ["რა მელის სიყვარულში?", "რას მირჩევ ამ კვირისთვის?"],
        "past": "წარსულში რთული პერიოდი გამოიარე და ამან ძალა შეგმატა.",
        "present": "ახლა არჩევანის წინ დგახარ და გული სწორ გზას გიჩვენებს.",
        "future": "წინ სასიამოვნო ამბავი და ახალი შეხვედრა გელოდება.",
        "symbol": ("გზა", "ახალი მიმართულება ცხოვრებაში."),
        "colors": [("იისფერი", "#8b6cff", "ინტუიცია და შინაგანი სიმშვიდე."), ("ოქროსფერი", "#e2bd6a", "თავდაჯერება და სითბო.")],
        "area": {"love": ("სიყვარული", "დღეს გულწრფელი საუბარი ურთიერთობას დაათბობს."),
                 "career": ("კარიერა", "საქმეში ერთ მთავარ ამოცანაზე გაამახვილე ყურადღება."),
                 "health": ("ჯანმრთელობა", "მეტი დაისვენე და საკმარისი წყალი დალიე."),
                 "finance": ("ფინანსები", "დიდ ხარჯებზე გადაწყვეტილებას დღეს ნუ მიიღებ."),
                 "communication": ("ურთიერთობა", "ერთმანეთის მოსმენა ამ კავშირს აძლიერებს."),
                 "trust": ("ნდობა", "ნდობა პატარა, მაგრამ მუდმივი საქციელით შენდება."),
                 "growth": ("ზრდა", "ერთად ახალი რამის სწავლა ორივეს გაგზრდით.")},
    },
    "ru": {
        "overview": "Твоя карта говорит о равновесии и внутренней силе.",
        "ascendant": "Лагна показывает, каким тебя видит мир: спокойным и уверенным.",
        "moon": "Луна говорит о твоих чувствах: ты глубокий человек и хорошо чувствуешь других.",
        "sun": "Солнце — твоя суть: у тебя есть воля и стремление к цели.",
        "navamsa": "Навамша указывает на верность в отношениях и цельную натуру.",
        "dasha": "Текущая даша — время терпения и медленного, но прочного роста.",
        "title": "Спокойное послание неба",
        "body": "Сегодня звёзды посылают тебе спокойную и ясную энергию. Не спеши, прислушайся к себе и действуй маленькими шагами.",
        "advice": "Сделай сегодня одно небольшое дело, которое давно откладываешь.",
        "word": "спокойствие", "lucky_color": "золотой",
        "keywords": ["спокойствие", "интуиция", "терпение"], "challenges": ["спешка", "сомнения"],
        "quote": "Твоё придёт к тебе в своё время.", "affirmation": "Я доверяю своему пути.",
        "purpose": "Твой путь — учиться и делиться с другими тем, что знаешь.",
        "love": "В любви главное — искренность и внимание к мелочам.",
        "career": "Успех в делах принесут терпение и последовательность.",
        "intention": "Загадай сегодня одно желание и сформулируй его ясно.",
        "steps": ["Зажги свечу и сделай несколько глубоких вдохов.", "Запиши своё желание на листе бумаги.",
                  "Сохрани листок до следующего полнолуния."],
        "avoid": "Избегай поспешных решений.",
        "answer": "Звёзды сейчас в дымке, поэтому отвечу коротко: доверься интуиции и двигайся шаг за шагом. Спроси меня чуть позже.",
        "follow_ups": ["Что ждёт меня в любви?", "Что посоветуешь на эту неделю?"],
        "past": "В прошлом ты прошёл трудный период, и он сделал тебя сильнее.",
        "present": "Сейчас ты стоишь перед выбором, и сердце подсказывает верный путь.",
        "future": "Впереди тебя ждут приятная новость и новая встреча.",
        "symbol": ("Дорога", "Новое направление в жизни."),
        "colors": [("Фиолетовый", "#8b6cff", "Интуиция и внутренний покой."), ("Золотой", "#e2bd6a", "Уверенность и тепло.")],
        "area": {"love": ("Любовь", "Искренний разговор сегодня согреет отношения."),
                 "career": ("Карьера", "Сосредоточься на одной главной задаче."),
                 "health": ("Здоровье", "Больше отдыхай и пей достаточно воды."),
                 "finance": ("Финансы", "Не принимай сегодня решений о крупных тратах."),
                 "communication": ("Общение", "Умение слушать друг друга укрепляет эту связь."),
                 "trust": ("Доверие", "Доверие строится маленькими, но постоянными поступками."),
                 "growth": ("Рост", "Учитесь новому вместе: это поможет расти обоим.")},
    },
    "en": {
        "overview": "Your chart speaks of balance and inner strength.",
        "ascendant": "The lagna shows how the world sees you: calm and confident.",
        "moon": "The Moon speaks of your feelings: you are deep and sense others well.",
        "sun": "The Sun is your core: you have will and a drive toward your goals.",
        "navamsa": "The navamsa points to loyalty in relationships and a whole, steady nature.",
        "dasha": "The current dasha is a time of patience and slow but solid growth.",
        "title": "A calm message from the sky",
        "body": "Today the stars send you calm and clear energy. Don't rush, listen to yourself and act in small steps.",
        "advice": "Do one small thing today that you have been putting off.",
        "word": "calm", "lucky_color": "gold",
        "keywords": ["calm", "intuition", "patience"], "challenges": ["haste", "doubt"],
        "quote": "What is yours will reach you in its own time.", "affirmation": "I trust my own path.",
        "purpose": "Your path is to learn and to share what you know.",
        "love": "In love, sincerity and attention to small things matter most.",
        "career": "Patience and steady work bring success.",
        "intention": "Make one wish today and put it into clear words.",
        "steps": ["Light a candle and take a few deep breaths.", "Write your wish on a piece of paper.",
                  "Keep the paper until the next full moon."],
        "avoid": "Avoid hasty decisions.",
        "answer": "The stars are hazy right now, so I'll keep it short: trust your intuition and move step by step. Ask me again a little later.",
        "follow_ups": ["What awaits me in love?", "What do you advise for this week?"],
        "past": "You went through a hard time, and it made you stronger.",
        "present": "You stand before a choice, and your heart shows the right way.",
        "future": "Pleasant news and a new meeting lie ahead.",
        "symbol": ("Road", "A new direction in life."),
        "colors": [("Violet", "#8b6cff", "Intuition and inner calm."), ("Gold", "#e2bd6a", "Confidence and warmth.")],
        "area": {"love": ("Love", "An honest talk will warm your relationship today."),
                 "career": ("Career", "Focus on one main task."),
                 "health": ("Health", "Rest more and drink enough water."),
                 "finance": ("Finance", "Don't decide on big purchases today."),
                 "communication": ("Communication", "Listening to each other makes this bond stronger."),
                 "trust": ("Trust", "Trust grows from small, steady actions."),
                 "growth": ("Growth", "Learning something new together helps you both grow.")},
    },
}
_BODY_FIELDS = {"summary", "text", "interpretation", "synthesis", "reading", "essence", "overview", "ascendant",
                "moon", "sun", "navamsa", "dasha", "meaning"}
_WORD_FIELDS = {"mood", "energy", "focus", "theme"}
_LIST_FIELDS = {"keywords": "keywords", "tags": "keywords", "strengths": "keywords", "challenges": "challenges",
                "steps": "steps", "follow_ups": "follow_ups"}


def _value(name: str, annotation, tx: dict):
    origin = get_origin(annotation)
    if annotation is bool:
        return True
    if annotation is int:
        return 3
    if origin is list:
        (inner,) = get_args(annotation)
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return _model_list(inner, tx)
        return list(tx[_LIST_FIELDS.get(name, "keywords")])
    if name in tx and isinstance(tx[name], str):
        return tx[name]
    if name in _WORD_FIELDS:
        return tx["word"]
    if name in ("position", "card_title"):
        return ""
    return tx["body"] if name in _BODY_FIELDS else tx["body"]


def _model_list(model: type[BaseModel], tx: dict) -> list[dict]:
    fields = model.model_fields
    if "area" in fields and get_origin(fields["area"].annotation) is Literal:
        return [{"area": a, "title": tx["area"][a][0], "text": tx["area"][a][1], "score": 3}
                for a in get_args(fields["area"].annotation)]
    if "hex" in fields:
        return [{"name": n, "hex": h, "meaning": m} for n, h, m in tx["colors"]]
    if "symbol" in fields:
        return [{"symbol": tx["symbol"][0], "meaning": tx["symbol"][1]}]
    return [{k: _value(k, f.annotation, tx) for k, f in fields.items()}]


def safe_payload(schema: type[BaseModel], lang: str) -> BaseModel:
    tx = T.get(lang, T["en"])
    return schema.model_validate({k: _value(k, f.annotation, tx) for k, f in schema.model_fields.items()})
