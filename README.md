# Biblioteca Personal con MongoDB

Aplicación de línea de comandos en Python que administra una biblioteca personal usando **MongoDB** (base de datos no relacional) a través del cliente oficial **pymongo**. Cada libro se guarda como un **documento JSON** dentro de la colección `libros`, en lugar de una fila en una tabla relacional.

## Funcionalidades

1. Agregar un libro (título, autor, género y estado de lectura).
2. Actualizar cualquier campo de un libro, incluido su estado de lectura.
3. Eliminar un libro (con confirmación).
4. Ver el listado completo de libros.
5. Buscar libros por título, autor o género (búsqueda parcial, sin distinguir mayúsculas).
6. Salir del programa.

## Estructura del proyecto

```
biblioteca_mongo/
├── biblioteca_mongo.py   # aplicación
├── requirements.txt      # dependencias
└── README.md             # este archivo
```

## Estructura del documento

```json
{
  "_id": "ObjectId generado por MongoDB",
  "titulo": "Cien años de soledad",
  "autor": "Gabriel García Márquez",
  "genero": "Novela",
  "leido": false,
  "fecha_registro": "2026-10-14T15:30:00Z"
}
```

| Campo            | Tipo     | Regla                                            |
|------------------|----------|--------------------------------------------------|
| `_id`            | ObjectId | Lo crea MongoDB automáticamente                  |
| `titulo`         | string   | Obligatorio, no vacío                            |
| `autor`          | string   | Obligatorio, no vacío                            |
| `genero`         | string   | Obligatorio, no vacío                            |
| `leido`          | bool     | Obligatorio: `true` (leído) o `false` (no leído) |
| `fecha_registro` | date     | La agrega la aplicación al crear el libro        |

## 1. Instalar MongoDB

Elige **una** de las opciones.

### Opción A: MongoDB local con Docker (la más sencilla)

Con Docker Desktop instalado:

```bash
docker run -d --name mongo-biblioteca -p 27017:27017 -v mongo_biblioteca:/data/db mongo:7
```

Para detenerlo o volver a iniciarlo: `docker stop mongo-biblioteca` / `docker start mongo-biblioteca`.

### Opción B: MongoDB Community Server instalado en el sistema

- **Windows:** descarga el instalador `.msi` desde la página oficial de MongoDB Community Server, ejecútalo y deja marcada la opción *Install MongoDB as a Service*. El servicio inicia solo.
- **macOS (Homebrew):**
  ```bash
  brew tap mongodb/brew
  brew install mongodb-community
  brew services start mongodb-community
  ```
- **Linux:** sigue la guía oficial de instalación para tu distribución en la documentación de MongoDB y luego inicia el servicio con `sudo systemctl start mongod`.

Comprueba que funciona (opcional, requiere `mongosh`): `mongosh --eval "db.runCommand({ ping: 1 })"`.

### Opción C: MongoDB Atlas (en la nube, plan gratuito)

1. Crea una cuenta en MongoDB Atlas y un clúster gratuito (M0).
2. En **Database Access**, crea un usuario de base de datos con su contraseña.
3. En **Network Access**, agrega tu dirección IP actual (o `0.0.0.0/0` solo para pruebas).
4. En **Database → Connect → Drivers**, copia la cadena de conexión.

## 2. Configurar la cadena de conexión

La aplicación lee la conexión de tres formas (de mayor a menor prioridad):

1. Argumentos: `--uri`, `--db`, `--coleccion`.
2. Variables de entorno: `MONGODB_URI`, `MONGODB_DB`, `MONGODB_COLLECTION`.
3. Valores por defecto: `mongodb://localhost:27017`, base `biblioteca`, colección `libros`.

Ejemplos de cadena de conexión:

```text
# Local (por defecto)
mongodb://localhost:27017

# Atlas
mongodb+srv://MI_USUARIO:MI_CONTRASENA@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

Si la contraseña contiene caracteres especiales (`@`, `:`, `/`, `#`, etc.), debes codificarlos (por ejemplo, `@` → `%40`).

Definir la variable de entorno:

```bash
# macOS / Linux
export MONGODB_URI="mongodb+srv://MI_USUARIO:MI_CONTRASENA@cluster0.xxxxx.mongodb.net/"

# Windows (PowerShell)
$env:MONGODB_URI = "mongodb+srv://MI_USUARIO:MI_CONTRASENA@cluster0.xxxxx.mongodb.net/"
```

> No subas tu contraseña a GitHub. Usa variables de entorno o pasa `--uri` por consola. La aplicación oculta la contraseña cuando muestra la URI en pantalla.

## 3. Instalar dependencias

Se recomienda un entorno virtual:

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Ejecutar la aplicación

```bash
python biblioteca_mongo.py
```

Con una URI explícita:

```bash
python biblioteca_mongo.py --uri "mongodb://localhost:27017" --db biblioteca --coleccion libros
```

## Ejemplos de uso

### Entradas válidas

```text
Elige una opción: 1
Título: El principito
Autor: Antoine de Saint-Exupéry
Género: Fábula
¿Ya lo leíste? (s/n): s
Libro agregado correctamente (id: 6700...).
```

- Estado de lectura: `s`, `si`, `sí` (leído) o `n`, `no` (no leído).
- Búsqueda: opción `5`, campo `2` (autor), texto `exup` → encuentra "Antoine de Saint-Exupéry".
- Actualizar: opción `2`, elegir el número del libro y presionar Enter en los campos que no cambian.

### Entradas inválidas (la aplicación las rechaza)

```text
Título:                      → "El campo no puede estar vacío."
¿Ya lo leíste? (s/n): tal vez → "Responde 's' (leído) o 'n' (no leído)."
Número del libro: 99         → "Elige un número entre 1 y N."
```

## Validaciones y manejo de errores

- **Error de conexión:** si MongoDB no está disponible, la URI es inválida o las credenciales son incorrectas, la aplicación muestra un mensaje claro y termina sin mostrar un traceback.
- **Conexión perdida durante el uso:** se informa el problema y se vuelve al menú.
- **Documentos mal estructurados:**
  - La aplicación valida los datos antes de enviarlos (textos no vacíos y `leido` booleano).
  - Al crear la colección se define un validador `$jsonSchema` en MongoDB, que rechaza documentos que no cumplan el esquema.
  - Si en la colección existen documentos incompletos (por ejemplo, insertados manualmente), el listado los marca con `[!] documento incompleto` en lugar de fallar.

## Verificar los datos en MongoDB (opcional)

```bash
mongosh
use biblioteca
db.libros.find().pretty()
```

## Solución de problemas

| Problema | Posible causa y solución |
|----------|--------------------------|
| `No se pudo conectar a MongoDB` | El servicio o contenedor no está iniciado, o el puerto 27017 está ocupado. En Atlas, agrega tu IP en *Network Access*. |
| `MongoDB rechazó las credenciales` | Usuario o contraseña incorrectos en la URI. |
| `La cadena de conexión no es válida` | La URI debe empezar con `mongodb://` o `mongodb+srv://`. |
| `Falta la librería pymongo` | Ejecuta `pip install -r requirements.txt` dentro del entorno virtual. |
