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

## Завършени етапи (Milestones)

- `m0-setup` — Начална структура, Django 5.2, DRF, React + Vite
- `m1-auth` — Custom User модел, профил с аватари, сесийна автентикация, CSRF защита
- `m2-question-bank` — Модели на въпроси (Choice & Numeric), категории, Django Admin, Fixture банка и тестове
