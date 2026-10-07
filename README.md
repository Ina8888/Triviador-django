# Quiz Conquest

Мултиплейър тривия стратегическа игра, разработена за курса по **Интернет програмиране**.


## Структура

```text
quiz-conquest/
├── backend/
│   ├── accounts/         
│   ├── config/          
│   ├── questions/    
│   │   ├── fixtures/
│   │   │   └── questions/
│   │   │       └── question_bank.json
│   │   ├── migrations/
│   │   ├── tests/
│   │   ├── admin.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   └── views.py
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/    # AuthModal и UI модули
│   │   ├── services/      # API клиент с автоматичен CSRF & Session поддръжка
│   │   ├── App.jsx        # Главен интерфейс на играта
│   │   └── App.css
│   ├── package.json
│   └── vite.config.js
└── .gitignore
```

---

## Инсталация и стартиране

### 1. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
```

#### Зареждане на началната банка с въпроси

```powershell
python manage.py loaddata questions/question_bank.json
```

#### Стартиране на тестовете

```powershell
python manage.py test questions
# или пълен набор от тестове:
python manage.py test
```

#### Стартиране на сървъра

```powershell
python manage.py runserver
```

Сървърът е достъпен на: `http://127.0.0.1:8000/`

---

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Приложението ще се зареди на: `http://localhost:5173/`

---

## Карта на проекта (M04 — Territories and Map)

Проектната карта съдържа **18 територии** (кратни на 3, между 9 и 21) с български географски и исторически имена, симетрични връзки и гарантирана свързаност на графа.

| № | Територия | Slug | Съседни територии (Neighbors) |
|---|---|---|---|
| 1 | Скали | `skali` | `dunaviya`, `sredets` |
| 2 | Дунавия | `dunaviya` | `skali`, `zhitno-pole`, `sredets` |
| 3 | Житно поле | `zhitno-pole` | `dunaviya`, `leventa`, `balkania` |
| 4 | Левента | `leventa` | `zhitno-pole`, `pelikania`, `madara` |
| 5 | Пеликания | `pelikania` | `leventa`, `kaliakra`, `madara` |
| 6 | Калиакра | `kaliakra` | `pelikania`, `madara`, `slanchevo` |
| 7 | Средец | `sredets` | `skali`, `dunaviya`, `ezera`, `balkania`, `rozova-dolina` |
| 8 | Балкания | `balkania` | `zhitno-pole`, `sredets`, `tsarevo`, `rozova-dolina` |
| 9 | Царево | `tsarevo` | `balkania`, `madara`, `chuden-kray`, `rozova-dolina` |
| 10 | Мадара | `madara` | `leventa`, `pelikania`, `kaliakra`, `tsarevo`, `chuden-kray` |
| 11 | Езера | `ezera` | `sredets`, `pirina`, `rozova-dolina` |
| 12 | Пирина | `pirina` | `ezera`, `zlaten-grozd`, `karakachan` |
| 13 | Розова долина | `rozova-dolina` | `sredets`, `balkania`, `tsarevo`, `ezera`, `zlaten-grozd` |
| 14 | Чуден край | `chuden-kray` | `tsarevo`, `madara`, `kukeri`, `slanchevo` |
| 15 | Златен грозд | `zlaten-grozd` | `rozova-dolina`, `pirina`, `karakachan`, `kukeri` |
| 16 | Кукери | `kukeri` | `zlaten-grozd`, `chuden-kray`, `karakachan`, `slanchevo` |
| 17 | Каракачан | `karakachan` | `pirina`, `zlaten-grozd`, `kukeri` |
| 18 | Слънчево | `slanchevo` | `kaliakra`, `chuden-kray`, `kukeri` |

> **Забележка**: Инициализацията на картата при създаване на игра и разпределението на столиците ще се извършват в **M05**. В M04 се въвеждат самите модели, дефиницията на графа, валидациите и защитите в Django Admin.

---

## Завършени етапи (Milestones)

- `m0-setup` — Начална структура, Django 5.2, DRF, React + Vite
- `m1-auth` — Custom User модел, профил с аватари, сесийна автентикация, CSRF защита
- `m2-question-bank` — Модели на въпроси (Choice & Numeric), категории, Django Admin, Fixture банка и тестове
- `m3-games-and-rounds` — Модели `Game`, `Player`, `Round`, constraints за 3 играчи, жизнен цикъл и тестове
- `m4-territories-and-map` — Модели `Territory` и `Capital`, 18-територийна проектна карта, валидация на графа, Django Admin и тестове
