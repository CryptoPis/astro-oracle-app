/* Oracle chamber: the stations (objects in the room) and the chamber's own texts in ka/en/ru.
   Every practice of the app is one object; `view` is the classic view the glass panel shows for it. */

export const STEP = Math.PI * 2 / 10;   // ten objects around the room, 36° apart

export const STATIONS = [
  { id: "tarot", view: "tarot", art: "tarot", slot: 0 },
  { id: "sphere", view: "sphere", art: "sphere", slot: 1 },
  { id: "moon", view: "moon", art: "moon", slot: 2 },
  { id: "advisor", view: "advisor", art: "advisor", slot: 3 },
  { id: "dream", view: "dream", art: "dream", slot: 4 },
  { id: "num", view: "num", art: "numerology", slot: 5 },
  { id: "chart", view: "kundli", alt: "compat", art: "kundli", slot: 6 },
  { id: "aura", view: "aura", art: "aura", slot: 7 },
  { id: "coffee", view: "coffee", art: "coffee", slot: 8 },
  { id: "gift", view: null, art: "day", slot: 9 },
];
/* not on the ring: the star dome above (swipe up) and the profile panel */
export const EXTRA = [
  { id: "horo", view: "horo", art: "week" },
  { id: "profile", view: "profile", art: "month" },
];
export const byId = (id) => STATIONS.find((s) => s.id === id) || EXTRA.find((s) => s.id === id);
export const stationOfView = (view) => STATIONS.find((s) => s.view === view || s.alt === view) || EXTRA.find((s) => s.view === view);

const TX = {
  ka: {
    st_tarot: "ტაროს მაგიდა", st_sphere: "ბროლის სფერო", st_moon: "მთვარის ფანჯარა", st_advisor: "მისნის სანთელი",
    st_dream: "სიზმრების წიგნი", st_num: "ასტროლაბი", st_chart: "ვარსკვლავთა გრაგნილი", st_aura: "აურის სარკე",
    st_coffee: "ყავის ფინჯანი", st_gift: "საჩუქრების ზარდახშა", st_horo: "ვარსკვლავების გუმბათი", st_profile: "პროფილი და პარამეტრები",
    sub_tarot: "დღის კარტი და სამკარტიანი გაშლა", sub_sphere: "დასვი კითხვა და გადაწმინდე ნისლი", sub_moon: "დღევანდელი მთვარის რიტუალი",
    sub_advisor: "ჰკითხე ორაკულს, ხმა ალიდან მოდის", sub_dream: "სიზმრის ახსნა და დღიური", sub_num: "ნუმეროლოგია და დღის რიცხვები",
    sub_chart: "კუნდლი და თავსებადობა", sub_aura: "აურა ფოტოთი", sub_coffee: "ყავის ნალექის მკითხაობა",
    sub_gift: "დღის საჩუქარი და სერია", sub_horo: "ჰოროსკოპი შენი რუკით და ცა ახლა", sub_profile: "დაბადების მონაცემები, ენა, ხმა, გრაფიკა",
    swipe: "გადაუსვი თითი და მიმოიხედე · შეეხე საგანს", up: "ზემოთ გადაუსვი: ვარსკვლავების გუმბათი", down: "ქვემოთ გადაუსვი: ოთახში დაბრუნება",
    domeTap: "შეეხე გუმბათს: შენი ჰოროსკოპი", compass: "ყველა პრაქტიკა", close: "დახურვა", toRoom: "ოთახში დაბრუნება",
    newToday: "დღეს ახალია", loading: "ოთახი ინთება…", lite: "მსუბუქი ვერსია", profile: "პროფილი",
    tierNow: "ახლა მუშაობს", gfxHigh: "მაღალი", gfxMedium: "საშუალო", gfxLite: "მსუბუქი", why_forced: "ხელით არჩეული", why_reduced: "შემცირებული მოძრაობა",
    why_desktop: "კომპიუტერი ან ვები", why_weak: "სუსტი მოწყობილობა", why_slowBefore: "ადრე ნელა მუშაობდა", why_noWebgl: "WebGL არ არის", why_slow: "ნელა მუშაობს",
    why_lost: "გრაფიკა გაითიშა", why_error: "შეცდომა",
    intro1: "ეს შენი მისნის ოთახია. თითის გადასმით მიმოიხედე.",
    intro2: "შეეხე საგანს და მისი პრაქტიკა გაიხსნება: კარტები, სფერო, სარკე, წიგნი…",
    intro3: "ზემოთ ვარსკვლავების გუმბათია შენი ჰოროსკოპით. კომპასში ყველა პრაქტიკა ერთადაა.",
    next: "შემდეგი", skip: "გამოტოვება", begin: "დავიწყოთ",
    birthday: "გილოცავ დაბადების დღეს! დღეს ოთახი შენთვის ოქროსფრად ანათებს.",
    tabKundli: "კუნდლი", tabCompat: "თავსებადობა",
  },
  en: {
    st_tarot: "Tarot table", st_sphere: "Crystal ball", st_moon: "Moon window", st_advisor: "The oracle's candle",
    st_dream: "Book of dreams", st_num: "Astrolabe", st_chart: "Star-chart scroll", st_aura: "Aura mirror",
    st_coffee: "Coffee cup", st_gift: "Gift chest", st_horo: "Star dome", st_profile: "Profile and settings",
    sub_tarot: "Card of the day and the three-card spread", sub_sphere: "Ask, then wipe the mist away", sub_moon: "Tonight's moon ritual",
    sub_advisor: "Ask the oracle: the voice comes from the flame", sub_dream: "Dream reading and journal", sub_num: "Numerology and the numbers of the day",
    sub_chart: "Kundli and compatibility", sub_aura: "Aura from a photo", sub_coffee: "Coffee grounds reading",
    sub_gift: "Daily gift and streak", sub_horo: "Your horoscope from your chart, and the sky now", sub_profile: "Birth data, language, sound, graphics",
    swipe: "Swipe to look around · touch an object", up: "Swipe up: the star dome", down: "Swipe down: back to the room",
    domeTap: "Touch the dome: your horoscope", compass: "All practices", close: "Close", toRoom: "Back to the room",
    newToday: "New today", loading: "The chamber is lighting up…", lite: "Light version", profile: "Profile",
    tierNow: "Running now", gfxHigh: "High", gfxMedium: "Medium", gfxLite: "Lite", why_forced: "chosen by hand", why_reduced: "reduce motion",
    why_desktop: "desktop or web", why_weak: "weak device", why_slowBefore: "slow earlier", why_noWebgl: "no WebGL", why_slow: "too slow",
    why_lost: "graphics lost", why_error: "error",
    intro1: "This is your oracle's chamber. Swipe to look around.",
    intro2: "Touch an object to open its practice: the cards, the sphere, the mirror, the book…",
    intro3: "Above you is the star dome with your horoscope. The compass lists every practice.",
    next: "Next", skip: "Skip", begin: "Let's begin",
    birthday: "Happy birthday! Today the chamber glows gold for you.",
    tabKundli: "Kundli", tabCompat: "Compatibility",
  },
  ru: {
    st_tarot: "Стол таро", st_sphere: "Хрустальный шар", st_moon: "Лунное окно", st_advisor: "Свеча оракула",
    st_dream: "Книга снов", st_num: "Астролябия", st_chart: "Звёздный свиток", st_aura: "Зеркало ауры",
    st_coffee: "Кофейная чашка", st_gift: "Сундук с подарком", st_horo: "Звёздный купол", st_profile: "Профиль и настройки",
    sub_tarot: "Карта дня и расклад на три карты", sub_sphere: "Задай вопрос и сотри туман", sub_moon: "Лунный ритуал на сегодня",
    sub_advisor: "Спроси оракула: голос звучит из пламени", sub_dream: "Толкование снов и дневник", sub_num: "Нумерология и числа дня",
    sub_chart: "Кундли и совместимость", sub_aura: "Аура по фото", sub_coffee: "Гадание на кофейной гуще",
    sub_gift: "Подарок дня и серия", sub_horo: "Гороскоп по твоей карте и небо сейчас", sub_profile: "Данные рождения, язык, звук, графика",
    swipe: "Проведи пальцем, чтобы осмотреться · коснись предмета", up: "Проведи вверх: звёздный купол", down: "Проведи вниз: назад в комнату",
    domeTap: "Коснись купола: твой гороскоп", compass: "Все практики", close: "Закрыть", toRoom: "Назад в комнату",
    newToday: "Новое сегодня", loading: "Комната зажигается…", lite: "Лёгкая версия", profile: "Профиль",
    tierNow: "Сейчас работает", gfxHigh: "Высокая", gfxMedium: "Средняя", gfxLite: "Лёгкая", why_forced: "выбрано вручную", why_reduced: "уменьшение движения",
    why_desktop: "компьютер или веб", why_weak: "слабое устройство", why_slowBefore: "раньше было медленно", why_noWebgl: "нет WebGL", why_slow: "слишком медленно",
    why_lost: "графика отключилась", why_error: "ошибка",
    intro1: "Это твоя комната оракула. Проведи пальцем, чтобы осмотреться.",
    intro2: "Коснись предмета, и откроется его практика: карты, шар, зеркало, книга…",
    intro3: "Над тобой звёздный купол с твоим гороскопом. В компасе собраны все практики.",
    next: "Далее", skip: "Пропустить", begin: "Начнём",
    birthday: "С днём рождения! Сегодня комната светится золотом для тебя.",
    tabKundli: "Кундли", tabCompat: "Совместимость",
  },
};

/* chamber text first, then the app's own i18n (so practice names stay identical in both interfaces) */
export function makeT(B) {
  return (k, vars) => {
    let s = (TX[B.S.lang] && TX[B.S.lang][k]) ?? TX.en[k];
    if (s == null) return B.t(k, vars);
    if (vars) for (const [a, b] of Object.entries(vars)) s = s.replace(`{${a}}`, b);
    return s;
  };
}
export const TEXTS = TX;   // tests check that ka/en/ru have the same keys
