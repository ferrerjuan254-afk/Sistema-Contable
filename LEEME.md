# Sistema Contable

Aplicación de escritorio (Windows) para gestión contable, construida con Python, PyQt6 y MySQL.

## Stack tecnológico

| Capa       | Tecnología                  |
|------------|-----------------------------|
| Frontend   | PyQt6                       |
| ORM        | SQLAlchemy 2.x              |
| Migración  | Alembic                     |
| Base datos | MySQL                       |
| Reportes   | ReportLab + openpyxl        |

## Módulos

- Multiempresa / Multisede
- Contabilidad General (PUC, asientos, mayor)
- Facturación
- Tesorería
- Nómina
- Seguridad Social (salud, pensión, ARL, parafiscales)
- Impuestos
- Reportes (PDF y Excel)

## Instalación

```bash
# 1. Clonar o descomprimir el proyecto
# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar base de datos
cp .env.example .env
# Editar .env con tus credenciales MySQL

# 5. Ejecutar
python main.py
```

## Estructura

```
contable/
├── config/          # Configuración y variables de entorno
├── core/
│   ├── database.py  # Engine SQLAlchemy
│   └── models/      # Modelos ORM (una DB, empresa_id en todas las tablas)
├── modules/         # Lógica de negocio por módulo
├── ui/              # Ventanas y componentes PyQt6
└── utils/           # Exportadores, validadores
```
