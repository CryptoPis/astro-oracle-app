"""Magic sphere: hand-written answers and advice (no AI call: instant, free, never garbled).

Each language is written natively, not translated from the Magic 8-Ball phrases. Tones: yes (gold glow),
wait (violet: unclear), no (silver: not now). A short piece of advice follows the answer and fits the topic
of the question (love / work / money / general), detected by simple keywords.
"""
import secrets

ANSWERS = {
    "ka": {
        "yes": ["ვარსკვლავები გიღიმიან: დიახ.", "გული სწორად გკარნახობს. ასე იქნება.", "კარი უკვე იღება, შედი თამამად.",
                "დიახ, და ეს სიხარულს მოგიტანს.", "ცა შენს მხარესაა.", "ნიშნები ნათელია: ეს შენი გზაა.",
                "დიახ. ენდე იმას, რასაც გრძნობ.", "სიკეთე უკვე გზაშია შენკენ."],
        "wait": ["ნისლი ჯერ არ გაფანტულა. ცოტა მოიცადე.", "პასუხი შენშივეა. მოუსმინე გულს.",
                 "ვარსკვლავები ჯერ დუმან. ხვალ ისევ მკითხე.", "ყველაფერი შენს შემდეგ ნაბიჯზეა დამოკიდებული.",
                 "დრო ჯერ არ მოსულა, მაგრამ ახლოსაა.", "გზა ორად იყოფა. აირჩიე ის, რომელიც გამშვიდებს.",
                 "ჯერ ადრეა. ნუ აჩქარებ მოვლენებს.", "ცა ჯერ ფიქრობს. დაელოდე ნიშანს."],
        "no": ["ახლა არა. ვარსკვლავები სხვა გზას გიჩვენებენ.", "ამჯერად არა, მაგრამ უკეთესი რამ გელოდება.",
               "ეს კარი დაკეტილია. სხვა გაიღება.", "ნუ დაიხარჯები ამაზე. შენი ძალა სხვაგან გჭირდება.",
               "ჯერ არა. დრო შენს სასარგებლოდ იმუშავებს.", "ცა გირჩევს, შეჩერდე და ხელახლა იფიქრო.",
               "არა ახლა. დაისვენე და ძალა მოიკრიბე.", "ეს შენი გზა არ არის. გაუშვი მსუბუქად."],
    },
    "en": {
        "yes": ["The stars are smiling: yes.", "Your heart already knows. It will be so.", "The door is opening. Walk through it.",
                "Yes, and it will bring you joy.", "The sky is on your side.", "The signs are clear: this is your path.",
                "Yes. Trust what you feel.", "Good things are already on their way to you."],
        "wait": ["The mist hasn't lifted yet. Wait a little.", "The answer is within you. Listen to your heart.",
                 "The stars are silent for now. Ask me again tomorrow.", "It all depends on your next step.",
                 "The time hasn't come yet, but it's near.", "The road divides. Choose the way that brings you peace.",
                 "It's too early. Don't rush what is unfolding.", "The sky is still deciding. Wait for a sign."],
        "no": ["Not now. The stars point to another path.", "Not this time, but something better is waiting.",
               "This door is closed. Another one will open.", "Don't spend yourself on this. Your strength is needed elsewhere.",
               "Not yet. Time will work in your favor.", "The sky advises you to pause and think again.",
               "Not now. Rest and gather your strength.", "This isn't your path. Let it go lightly."],
    },
    "ru": {
        "yes": ["Звёзды улыбаются тебе: да.", "Сердце уже знает ответ. Так и будет.", "Дверь открывается, смело входи.",
                "Да, и это принесёт тебе радость.", "Небо на твоей стороне.", "Знаки ясны: это твой путь.",
                "Да. Доверься своим чувствам.", "Хорошее уже спешит к тебе."],
        "wait": ["Туман ещё не рассеялся. Подожди немного.", "Ответ внутри тебя. Прислушайся к сердцу.",
                 "Звёзды пока молчат. Спроси меня завтра.", "Всё зависит от твоего следующего шага.",
                 "Время ещё не пришло, но оно близко.", "Дорога расходится. Выбери ту, что дарит покой.",
                 "Ещё рано. Не торопи события.", "Небо ещё решает. Дождись знака."],
        "no": ["Не сейчас. Звёзды указывают другой путь.", "В этот раз нет, но тебя ждёт нечто лучшее.",
               "Эта дверь закрыта. Откроется другая.", "Не трать силы на это. Они нужны тебе в другом месте.",
               "Пока нет. Время сыграет тебе на руку.", "Небо советует остановиться и подумать ещё раз.",
               "Не сейчас. Отдохни и набирайся сил.", "Это не твой путь. Отпусти легко."],
    },
}

ADVICE = {
    "ka": {
        ("love", "yes"): "სიყვარულში გაბედე: ერთი თბილი სიტყვა ბევრს შეცვლის.",
        ("love", "wait"): "ნუ ჩქარობ. სიყვარულს მოთმინება და ყურადღება სჭირდება.",
        ("love", "no"): "პირველ რიგში საკუთარ თავს გაუფრთხილდი. შენ სითბოს იმსახურებ.",
        ("work", "yes"): "იმოქმედე თამამად: შენი შრომა დაფასდება.",
        ("work", "wait"): "დაგეგმე შემდეგი ნაბიჯი და დაელოდე სწორ მომენტს.",
        ("work", "no"): "ახლა ძალა სხვა საქმეს მოახმარე. ეს გზა მოგვიანებით გაიხსნება.",
        ("money", "yes"): "ფინანსებში იღბალი გაქვს, მაგრამ გონივრულად დახარჯე.",
        ("money", "wait"): "დიდი ხარჯის ცოტა ხნით გადადება სჯობს.",
        ("money", "no"): "ამ ხარჯს მოერიდე. ფული უფრო საჭირო რამისთვის შეინახე.",
        ("general", "yes"): "ენდე ინტუიციას და პირველი ნაბიჯი დღესვე გადადგი.",
        ("general", "wait"): "დღეს წვრილმან ნიშნებს დააკვირდი: პასუხი იქ იმალება.",
        ("general", "no"): "გაუშვი ის, რაც გამძიმებს, და ადგილი ახალს დაუთმე.",
    },
    "en": {
        ("love", "yes"): "Be brave in love: one warm word can change a lot.",
        ("love", "wait"): "Don't rush. Love needs patience and attention.",
        ("love", "no"): "Take care of yourself first. You deserve warmth.",
        ("work", "yes"): "Act boldly: your work will be noticed.",
        ("work", "wait"): "Plan your next step and wait for the right moment.",
        ("work", "no"): "Put your energy into another task for now. This road will open later.",
        ("money", "yes"): "Luck is with your finances, but spend wisely.",
        ("money", "wait"): "Better to put a big purchase off for a while.",
        ("money", "no"): "Avoid this expense. Save the money for something you really need.",
        ("general", "yes"): "Trust your intuition and take the first step today.",
        ("general", "wait"): "Notice the small signs today: the answer is hiding there.",
        ("general", "no"): "Let go of what weighs you down and make room for something new.",
    },
    "ru": {
        ("love", "yes"): "Будь смелее в любви: одно тёплое слово может многое изменить.",
        ("love", "wait"): "Не торопись. Любви нужны терпение и внимание.",
        ("love", "no"): "Сначала позаботься о себе. Ты заслуживаешь тепла.",
        ("work", "yes"): "Действуй смело: твой труд оценят.",
        ("work", "wait"): "Спланируй следующий шаг и дождись подходящего момента.",
        ("work", "no"): "Пока направь силы на другое дело. Этот путь откроется позже.",
        ("money", "yes"): "Удача на стороне твоих финансов, но трать разумно.",
        ("money", "wait"): "Крупную покупку лучше ненадолго отложить.",
        ("money", "no"): "Избегай этой траты. Сбереги деньги для действительно нужного.",
        ("general", "yes"): "Доверься интуиции и сделай первый шаг уже сегодня.",
        ("general", "wait"): "Присмотрись сегодня к мелким знакам: ответ прячется в них.",
        ("general", "no"): "Отпусти то, что тебя тяготит, и освободи место для нового.",
    },
}

# word stems, matched anywhere in the lowercased question (Georgian has no case, so stems cover the forms)
TOPICS = {
    "love": ["უყვარ", "სიყვარ", "შეყვარ", "ვუყვარ", "მიყვარ", "მომწონ", "მოვწონ", "ბიჭ", "გოგო", "ქმარ", "ცოლ",
             "ურთიერთობ", "პაემან", "ქორწ", "დავშორ", "შევრიგ", "გული",
             "love", "boyfriend", "girlfriend", "crush", "relationship", "marry", "marri", "date", "partner",
             "husband", "wife", "ex ", "like me",
             "люб", "парен", "девуш", "отношен", "муж", "жен", "свидан", "брак", "нрав", "встреч"],
    "work": ["სამსახ", "სამუშაო", "საქმე", "კარიერ", "ბოს", "უფროს", "დაწინაურ", "გამოცდ", "სწავლ", "ინტერვიუ", "პროექტ",
             "job", "work", "career", "boss", "promotion", "exam", "interview", "project", "study",
             "работ", "карьер", "начальн", "повышен", "экзамен", "собеседован", "проект", "учёб", "учеб"],
    "money": ["ფულ", "ხელფას", "ვალ", "სესხ", "ვიყიდ", "ვყიდ", "გავყიდ", "ყიდვ", "შემოსავ", "ბიზნეს", "ინვესტ", "ლატარ", "მოგებ",
              "money", "salary", "debt", "loan", "buy", "sell", "income", "business", "invest", "lottery", "rich",
              "деньг", "зарплат", "долг", "кредит", "купи", "купл", "прода", "доход", "бизнес", "инвест", "лотере"],
}
TONE_WEIGHTS = [("yes", 5), ("wait", 4), ("no", 3)]
_rng = secrets.SystemRandom()


def topic_of(question: str | None) -> str:
    q = f" {(question or '').lower()} "
    for topic in ("love", "money", "work"):   # money before work: "will I get the salary at work" is about money
        if any(stem in q for stem in TOPICS[topic]):
            return topic
    return "general"


def ask(lang: str, question: str | None) -> dict:
    lang = lang if lang in ANSWERS else "en"
    tone = _rng.choices([t for t, _ in TONE_WEIGHTS], weights=[w for _, w in TONE_WEIGHTS])[0]
    topic = topic_of(question)
    return {"answer": _rng.choice(ANSWERS[lang][tone]), "tone": tone, "topic": topic, "advice": ADVICE[lang][(topic, tone)]}
