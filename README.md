# Generador y editor de Estimates de HighLevel — versión 3

La aplicación local consulta cotizaciones de HighLevel, permite crear/editar borradores y genera un PDF propio en español. De forma predeterminada filtra cotizaciones con estado `draft`.

## 1. Probar sin credenciales

Haz clic derecho sobre `run.ps1` y selecciona **Ejecutar con PowerShell**, o abre PowerShell en esta carpeta y ejecuta:

```powershell
.\run.ps1
```

Abre `http://127.0.0.1:8765`. Verás una cotización de demostración. Usa **Vista previa** o **Descargar PDF**.

Detén el servidor con `Ctrl+C`.

## 2. Crear acceso en HighLevel

Dentro de la subcuenta que contiene las cotizaciones:

1. Ve a **Settings > Private Integrations**.
2. Selecciona **Create New Integration**.
3. Usa el nombre `Generador PDF Cotizaciones`.
4. Habilita `invoices/estimate.readonly` y `invoices/estimate.write`.
5. Añade `contacts.readonly` si vas a consultar campos personalizados del contacto.
6. Añade `opportunities.readonly` si vas a usar datos del proyecto guardados en una oportunidad.
7. Guarda y copia el token. HighLevel solo lo muestra una vez.
8. Obtén el **Location ID** de esa misma subcuenta.

No compartas el token ni lo pegues en páginas web, chats o código público.

## 3. Configurar la aplicación

1. Duplica `config.example.json`.
2. Nombra la copia `config.local.json`.
3. Reemplaza los valores de `location_id` y `token`.
4. Conserva las comillas y no agregues una coma después del último campo.

Ejemplo estructural:

```json
{
  "location_id": "abc123",
  "token": "tu-token-privado",
  "port": 8765
}
```

`config.local.json` está excluido de Git para evitar publicar el secreto accidentalmente.

## 4. Crear un borrador para la prueba

En HighLevel:

1. Abre **Payments > Invoices & Estimates > Estimates**.
2. Crea una cotización y selecciona un contacto existente.
3. Agrega al menos un concepto.
4. Guarda como borrador.
5. No pulses **Send**.

Después inicia la aplicación y pulsa **Consultar** con el estado **Borrador**. Puedes dejar vacío el ID del contacto para consultar todos los borradores o introducirlo para limitar la búsqueda.

## 5. Qué hace el programa

En la pantalla de resultados puedes usar **Nueva cotización** para crear un estimate o **Editar** para modificar uno existente. El editor permite cambiar nombre, número, fechas, cliente, términos y partidas. El botón **Guardar en HighLevel** usa `POST /invoices/estimate` para una cotización nueva y `PUT /invoices/estimate/{estimateId}` para una existente.

La aplicación llama a:

```text
GET https://services.leadconnectorhq.com/invoices/estimate/list
```

con los parámetros `altId`, `altType=location`, `status`, `limit` y `offset`. El token se usa únicamente en el proceso Python. El navegador nunca lo recibe.

Los datos JSON recibidos de HighLevel se transforman en un PDF A4 con etiquetas en español, moneda de la cotización, cliente, conceptos, subtotal, descuento, IVA, total, vigencia y términos.

## Solución de problemas

- **Modo demo:** no existe `config.local.json`, o el token/Location ID están vacíos.
- **401 Unauthorized:** token incorrecto, vencido o perteneciente a otra subcuenta.
- **403 Forbidden:** falta `invoices/estimate.readonly` para leer o `invoices/estimate.write` para crear/editar.
- **No hay resultados:** confirma que la cotización está en `draft` y en la misma subcuenta.
- **HighLevel devolvió identificadores sin detalle:** conserva la respuesta completa del endpoint de creación o adapta `HighLevelClient.list_estimates` al formato real devuelto por tu cuenta. La documentación pública tipa el contenido del arreglo de manera poco específica.
- **Falta ReportLab:** ejecuta `python -m pip install reportlab`.

## Seguridad

- Ejecuta el programa únicamente en `127.0.0.1`; no lo publiques directamente en Internet.
- Concede permisos de escritura solo si utilizarás el editor; para solo PDF basta `invoices/estimate.readonly`.
- No guardes el token en JavaScript ni en HTML.
- Rota el token si sospechas que fue expuesto.
- Para una aplicación multiusuario o pública, usa OAuth 2.0 y autenticación propia.
