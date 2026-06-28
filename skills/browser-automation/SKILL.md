# Browser Automation Skill

Automatización de navegadores combinando CDP CLI + MCP Desktop + Bitwarden.

## Herramientas Disponibles

### 1. CDP CLI (puerto 9222)
Comandos directos vía Chrome DevTools Protocol:

## CLI Tool (agentbrowser-cli)

Herramienta unificada que combina CDP + Desktop + Bitwarden:

```bash
# Listar pestañas
agentbrowser-cli.py tabs

# Navegar
agentbrowser-cli.py navigate https://google.com

# Rellenar campo
agentbrowser-cli.py fill "#email" "user@test.com"

# Hacer clic
agentbrowser-cli.py click "button[type=submit]"

# Evaluar JavaScript
agentbrowser-cli.py eval "document.title"

# Screenshot
agentbrowser-cli.py screenshot output.png

# Snapshot de accesibilidad
agentbrowser-cli.py snapshot

# Convertir página a Markdown
agentbrowser-cli.py markdown https://example.com
agentbrowser-cli.py markdown  # Página actual

# Renderizar Markdown en terminal
agentbrowser-cli.py render "# Título\n- Item 1\n- Item 2"

# Bitwarden
agentbrowser-cli.py bitwarden open
agentbrowser-cli.py bitwarden fill "user@email.com"
agentbrowser-cli.py bitwarden submit

# Desktop control
agentbrowser-cli.py desktop click 100 200
agentbrowser-cli.py desktop type "hola"
agentbrowser-cli.py desktop key "ctrl+a"
agentbrowser-cli.py desktop screenshot
agentbrowser-cli.py desktop windows
agentbrowser-cli.py desktop focus "Chromium"
```

# Navegación
cdp-cli go "page-id" "https://example.com"
cdp-cli go "page-id" back
cdp-cli go "page-id" reload

# Interacción
cdp-cli fill "page-id" "texto" "selector-css"
cdp-cli click "page-id" "selector-css"
cdp-cli key "page-id" enter

# Evaluación JavaScript
cdp-cli eval "page-id" "document.title"

# Snapshot (árbol de accesibilidad)
cdp-cli snapshot "page-id" --format ax

# Screenshot
cdp-cli screenshot "page-id" output.png
```

### 2. MCP Desktop Control (puerto 8787)
Control de escritorio vía HTTP:

```bash
# Mouse
curl -X POST http://127.0.0.1:8787/desktop/mouse/click -d '{"x":100,"y":200}'
curl -X POST http://127.0.0.1:8787/desktop/mouse/scroll -d '{"direction":"down","clicks":3}'

# Teclado
curl -X POST http://127.0.0.1:8787/desktop/keyboard/type -d '{"text":"hola"}'
curl -X POST http://127.0.0.1:8787/desktop/keyboard/press -d '{"keys":"ctrl+a"}'

# Ventanas
curl http://127.0.0.1:8787/desktop/windows
curl -X POST http://127.0.0.1:8787/desktop/windows/focus -d '"Chromium"'

# Screenshot
curl -X POST http://127.0.0.1:8787/desktop/screenshot -d '{"path":"/tmp/shot.png"}'
docker cp agentbrowser-browser:/tmp/shot.png /tmp/shot.png
```

### 3. Bitwarden (extensión en Chromium)
Gestión de credenciales:

```bash
# Abrir popup de Bitwarden vía CDP
cdp-cli eval "page-id" 'window.open("chrome-extension://gfjamknononjpebljlkikhlebkhjngge/popup/index.html")'

# O vía desktop control: click en icono puzzle → click en Bitwarden
# Coordenadas típicas: puzzle icon ≈ x:1260, y:166 (ajustar según resolución)
```

## Flujo de Trabajo Típico

### Rellenar formulario con credenciales de Bitwarden

1. **Listar pestañas**
   ```bash
   cdp-cli tabs --cdp-url http://localhost:9222
   ```

2. **Navegar al sitio**
   ```bash
   cdp-cli go "page-id" "https://sitio-web.com/login"
   ```

3. **Obtener snapshot para identificar campos**
   ```bash
   cdp-cli snapshot "page-id" --format ax
   ```

4. **Rellenar campos**
   ```bash
   cdp-cli fill "page-id" "usuario" "#email"
   cdp-cli fill "page-id" "contraseña" "#password"
   ```

5. **Hacer clic en submit**
   ```bash
   cdp-cli click "page-id" "button[type=submit]"
   ```

### Usar desktop control para UI que no se puede automatizar vía CDP

```bash
# Click en coordenadas específicas
curl -X POST http://127.0.0.1:8787/desktop/mouse/click -d '{"x":500,"y":300}'

# Typing con delay
curl -X POST http://127.0.0.1:8787/desktop/keyboard/type -d '{"text":"password123","delay_ms":30}'
```

## Instalación de CDP CLI

```bash
npm install -g @myerscarpenter/cdp-cli
export PATH="$PATH:/home/tuxed/.npm-global/bin"
```

## Notas Técnicas

- **Puerto CDP**: 9222 (interno) → 9223 (externo via proxy)
- **Puerto MCP**: 8787
- **Profile Chrome**: `/data/profile/chromium` (persistente en volumen Docker)
- **Extensiones**: `/opt/bitwarden-extension`
- **Resolución**: 1366x768 (configurable via `BROWSER_WINDOW_SIZE`)
- **Idioma**: es-ES (configurable via `BROWSER_LOCALE`)

## CLI Tool (agentbrowser-cli)

Herramienta unificada que combina CDP + Desktop + Bitwarden:

```bash
# Listar pestañas
python3 agentbrowser-cli.py tabs

# Navegar
python3 agentbrowser-cli.py navigate https://google.com

# Rellenar campo
python3 agentbrowser-cli.py fill "#email" "user@test.com"

# Hacer clic
python3 agentbrowser-cli.py click "button[type=submit]"

# Evaluar JavaScript
python3 agentbrowser-cli.py eval "document.title"

# Screenshot
python3 agentbrowser-cli.py screenshot output.png

# Snapshot de accesibilidad
python3 agentbrowser-cli.py snapshot

# Bitwarden
python3 agentbrowser-cli.py bitwarden open
python3 agentbrowser-cli.py bitwarden fill "user@email.com"
python3 agentbrowser-cli.py bitwarden submit

# Desktop control
python3 agentbrowser-cli.py desktop click 100 200
python3 agentbrowser-cli.py desktop type "hola"
python3 agentbrowser-cli.py desktop key "ctrl+a"
python3 agentbrowser-cli.py desktop screenshot
python3 agentbrowser-cli.py desktop windows
python3 agentbrowser-cli.py desktop focus "Chromium"
```

## Solución de Problemas

### Error "locale override" en MCP browser
Usar cdp-cli en su lugar:
```bash
cdp-cli eval "page-id" "document.title"
```

### Perfil bloqueado
```bash
docker exec -u root agentbrowser-browser rm -f /data/profile/chromium/SingletonLock
docker restart agentbrowser-browser
```

### X server no disponible
```bash
docker exec -u root agentbrowser-browser bash -c "rm -f /tmp/.X20-lock /tmp/.X11-unix/X20 && Xvfb :20 -screen 0 1366x768x24 -ac &"
```
