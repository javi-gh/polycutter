# Changelog

Todas las versiones notables de este proyecto se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado [SemVer](https://semver.org/lang/es/).

## [1.0.0] — 2026-11-17

Primera versión pública.

### Añadido
- Lazo editable sobre la superficie de la malla: arrastrar, insertar y borrar puntos.
- Cierre del lazo sin aplicar el corte; el corte se lanza con botón o `Ctrl+Enter`.
- HUD en la vista 3D y panel N sincronizados desde una única tabla de comandos.
- Modos **Dibujar** y **Mover**, con hover y borrado consistentes en ambos.
- Corte booleano robusto con fallback automático `MANIFOLD` → `EXACT`.
- Separación automática del resultado en las dos piezas mayores (`_A` y `_B`).
- Ajustes de escena: grosor de corte (mm), ocultar original, transparencia X-Ray.

### Rendimiento
- Caché del layout del HUD.
- Caché de proyecciones 3D→2D por vista.
- Caché de batches GPU por versión del lazo.

### Corregido
- El deshacer y «borrar todo» dejan de romper el tramo en curso.
- Sesiones huérfanas se auto-resetean en el panel (keepalive).
- Registro/desregistro tolerante a recarga del addon.
