<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/price_buddy/brand/dark_logo.png">
    <img src="custom_components/price_buddy/brand/logo.png" alt="Price Buddy" width="420">
  </picture>
</p>

# Price Buddy para Home Assistant

[English](README.md) · **Español**

Custom component para **[jez500/pricebuddy](https://github.com/jez500/pricebuddy)**. Crea un sensor por cada producto visible para el token de la API.

## Qué crea

Cada producto genera una entidad con:

- Estado: precio actual (`current_price`).
- Unidad: moneda configurada en Home Assistant o la indicada en las opciones.
- Imagen del producto, cuando existe.
- Atributos básicos: ID, estado, precio objetivo, porcentaje objetivo, favorito, etiquetas y fechas.
- En modo detallado: tienda más barata, URL de compra, stock, tendencia, última consulta, número de ofertas y moneda real de la tienda.

Los productos nuevos se añaden sin reiniciar Home Assistant. Cuando un producto se elimina de Price Buddy, su entidad queda no disponible para conservar el historial; puede borrarse después desde el registro de entidades.

## Instalación manual

1. Copia la carpeta `custom_components/price_buddy` a:

   ```text
   /config/custom_components/price_buddy
   ```

2. Reinicia Home Assistant.
3. Abre **Ajustes → Dispositivos y servicios → Añadir integración**.
4. Busca **Price Buddy**.

## Token de Price Buddy

En Price Buddy, abre el menú de usuario de la esquina superior derecha y entra en **API tokens**. Crea un token con permiso para listar o leer productos.

La integración acepta estas formas de URL:

```text
http://192.168.1.50:8080
http://192.168.1.50:8080/api
https://pricebuddy.example.com
```

No incluyas `/products`; si se incluye accidentalmente como `/api/products`, la integración lo corrige.

## Opciones

Desde **Configurar** en la integración se puede cambiar:

- Intervalo de actualización: entre 1 y 1440 minutos; por defecto, 15.
- Moneda alternativa: por defecto se usa la moneda configurada en Home Assistant.
- Datos detallados: desactivados por defecto para reducir el tráfico. Al activarlos Price Buddy devuelve también `price_cache`, que puede contener bastante histórico.

## Ejemplo

Un producto llamado “Cafetera” creará una entidad parecida a:

```text
sensor.price_buddy_192_168_1_50_cafetera
```

El identificador exacto lo asigna Home Assistant y puede cambiarse desde la interfaz.

## Compatibilidad

- Home Assistant 2025.1 o posterior.
- Price Buddy con la API REST de productos disponible en `/api/products`.
- No necesita dependencias Python externas; usa la sesión HTTP compartida de Home Assistant.

## Solución de problemas

- **Token no válido**: genera otro token y asegúrate de copiarlo completo.
- **Permisos insuficientes**: concede al token permiso de lectura o listado de productos.
- **Respuesta no compatible**: verifica que la URL apunta a la instalación `jez500/pricebuddy` y no a otra aplicación con el mismo nombre.
- **Certificado autofirmado**: desactiva la verificación SSL solo en una red de confianza.

## Evento de cambio de precio

Cada vez que cambia el precio de un producto, la integración lanza el evento `price_buddy_price_changed` con `entity_id`, `product_id`, `name`, `old_price`, `new_price`, `currency`, `target_price`, `target_reached`, `store` y `url`. Sirve para crear automatizaciones de aviso.
