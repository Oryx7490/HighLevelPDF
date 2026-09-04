# HighLevelPDF — versión 2

Aplicación local para Windows que consulta cotizaciones de HighLevel y genera
archivos PDF en español.

## Cambios de la versión 2

- Se eliminó la columna visible de impuesto por producto.
- La columna **Descripción** aumentó de 91 mm a 103 mm.
- El resumen utiliza la etiqueta **IVA** en lugar de “Impuestos”.
- Se conservan **Subtotal, Descuento, IVA y Total**.

Los documentos PDF generados anteriormente no cambian automáticamente. Para
aplicar el nuevo formato es necesario generar o reenviar el PDF.

## Instalar o actualizar en Windows

1. Descarga o clona este repositorio.
2. Conserva todos los archivos dentro de la misma carpeta.
3. Ejecuta `Instalar.cmd` con doble clic.
4. Abre el acceso directo **Cotizaciones HighLevel** creado en el Escritorio.

Si ya existe una instalación, vuelve a ejecutar `Instalar.cmd`. El instalador
actualiza el programa y conserva las credenciales guardadas en
`config.local.json`.

## Configuración inicial

La primera instalación abre `config.local.json`. Completa `location_id` y
`token`, guarda el archivo y abre nuevamente la aplicación. Nunca publiques ni
compartas ese archivo.

## Descargar mediante Git

```powershell
git clone https://github.com/Oryx7490/HighLevelPDF.git
cd HighLevelPDF
.\Instalar.cmd
```

Para actualizar una copia descargada anteriormente:

```powershell
git pull origin main
.\Instalar.cmd
```
