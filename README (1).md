```md
# UF_HD-app

Short description: Εφαρμογή για υποστήριξη ασφαλούς υπερδιήθησης σε αιμοκαθαιρόμενους ασθενείς.

Prerequisites
- Python 3.8+ (ή ό,τι απαιτεί το project)
- pip, virtualenv
- (προαιρετικά) PostgreSQL / άλλες υπηρεσίες αν το project τις χρειάζεται

Quick start (local)
1. python -m venv .venv
2. .\.venv\Scripts\activate
3. pip install -r requirements.txt
4. set required ENV vars (π.χ. copy .env.example -> .env)
5. python run.py  (ή το command που εκκινεί το app)

Notes
- Μην ανεβάζετε αρχεία με πραγματικά δεδομένα ασθενών. Χρησιμοποιήστε example fixtures.
- Για deploy, προτείνεται Docker ή managed cloud service.
```