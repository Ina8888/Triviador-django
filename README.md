# Quiz Conquest

Мултиплейър тривия стратегическа игра, разработена за курса по **Интернет програмиране**.

## Технологичен стек

- **Backend**: Python 3.11+, Django 5.2 LTS, Django REST Framework
- **База данни**: SQLite
- **Frontend**: React, Vite
- **Автентикация**: Django Session Authentication с CSRF защита

---

## Структура на проекта

```text
quiz-conquest/
├── backend/
│   ├── accounts/          # Milestone 1: Custom User & Profile, Session Auth, API
│   ├── config/            # Основни Django настройки и routing
│   ├── questions/         # Milestone 2: Категории, Въпроси, Фикстури, Admin
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

#### Зареждане на началната банка с въпроси (Fixture)

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

## Завършени етапи (Milestones)

- `m0-setup` — Начална структура, Django 5.2, DRF, React + Vite
- `m1-auth` — Custom User модел, профил с аватари, сесийна автентикация, CSRF защита
- `m2-question-bank` — Модели на въпроси (Choice & Numeric), категории, Django Admin, Fixture банка и тестове
