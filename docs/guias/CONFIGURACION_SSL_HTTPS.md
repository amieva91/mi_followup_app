# 🔒 Configuración SSL/HTTPS - followup.fit

**Última actualización**: 12 Noviembre 2025  
**Estado**: ✅ Documentación en progreso

---

## 📋 Información General

**Dominio**: `followup.fit`  
**URL Producción**: `https://followup.fit/`  
**Servidor**: Oracle Cloud (140.238.120.92)  
**Usuario**: `ubuntu`

---

## ✅ Información Confirmada

### 1. Tipo de Certificado

✅ **Let's Encrypt** (gratuito)
- **Emisor**: Let's Encrypt E5
- **Certificado Intermedio**: ISRG Root X1
- **Validez**: 3 meses (típico de Let's Encrypt)
- **Dominios cubiertos**: `followup.fit` y `www.followup.fit`

### 2. Ubicación del Certificado

✅ **Load Balancer de Oracle Cloud**
- **Load Balancer**: `CarlosAmieva-LB`
- **Listener HTTPS**: `listener_lb_2025-0512-0852`
- **Puerto**: 443
- **Configuración**:
  - **Use SSL**: Yes
  - **Certificate resource**: Load balancer managed certificate
  - **Certificate name**: `carlosamieva-cert`
  - **Cipher suite**: `oci-compatible-ssl-cipher-suite-v1`
  - **Enable session resumption**: Yes
  - **Verify peer certificate**: No

### 3. Herramientas Utilizadas

✅ **Certbot (Let's Encrypt)**
- **Ubicación**: Servidor Ubuntu (140.238.120.92)
- **Ruta**: `/usr/bin/certbot`
- **Versión**: `2.9.0`
- **Paquetes instalados**:
  - `certbot` (2.9.0-1)
  - `python3-certbot` (2.9.0-1)
- **Proceso**: Certificado generado en servidor con Certbot → Importado al Load Balancer de Oracle Cloud

### 4. Certificados en el Servidor

✅ **Certificados encontrados en `/etc/letsencrypt/live/`**:

1. **`followup.fit-0001`** (EXPIRADO)
   - Dominios: `followup.fit`
   - Expiración: 2025-08-10 08:25:44+00:00
   - Ruta certificado: `/etc/letsencrypt/live/followup.fit-0001/fullchain.pem`
   - Ruta clave privada: `/etc/letsencrypt/live/followup.fit-0001/privkey.pem`
   - Tipo de clave: ECDSA

2. **`followup.fit`** (EXPIRADO - Probablemente el activo en LB)
   - Dominios: `followup.fit` y `www.followup.fit`
   - Expiración: 2025-08-10 07:40:33+00:00
   - Ruta certificado: `/etc/letsencrypt/live/followup.fit/fullchain.pem`
   - Ruta clave privada: `/etc/letsencrypt/live/followup.fit/privkey.pem`
   - Tipo de clave: ECDSA
   - **Nota**: Este certificado cubre ambos dominios y probablemente es el que está importado en el Load Balancer

3. **`www.followup.fit`** (EXPIRADO)
   - Dominios: `www.followup.fit`
   - Expiración: 2025-08-10 08:26:10+00:00
   - Ruta certificado: `/etc/letsencrypt/live/www.followup.fit/fullchain.pem`
   - Ruta clave privada: `/etc/letsencrypt/live/www.followup.fit/privkey.pem`
   - Tipo de clave: ECDSA

**Observación**: Todos los certificados muestran como expirados en la salida de `certbot certificates`, pero el certificado en el Load Balancer está activo. Esto sugiere que:
- El certificado fue renovado y reimportado manualmente, O
- El certificado en el LB es más reciente que los del servidor

### 5. Renovación Automática

✅ **Timer de systemd configurado**:
- **Servicio**: `certbot.timer`
- **Estado**: Activo y habilitado
- **Frecuencia**: Dos veces al día
- **Última ejecución**: 16 Nov 2025 17:59:32 UTC
- **Próxima ejecución**: Programada automáticamente

⚠️ **Problema detectado**: Las renovaciones automáticas están **fallando**
- **Error**: "All renewals failed" (16 Nov 2025)
- **Certificados afectados**: Los 3 certificados en el servidor
- **Causa probable**: Los certificados fueron generados con un método de validación que ya no está disponible (probablemente `standalone` o `webroot` que requiere que el servidor esté accesible directamente, pero ahora el tráfico pasa por el Load Balancer)

**Observación importante**: 
- Los certificados en el servidor están expirados (desde agosto 2025)
- El certificado en el Load Balancer está activo y funcionando
- Esto sugiere que el certificado fue renovado **manualmente** y **reimportado** al Load Balancer

### 6. Proceso de Importación al Load Balancer

✅ **Método**: Consola web de Oracle Cloud

**Ubicación en la consola**:
- Oracle Cloud Console → Networking → Load Balancers
- Seleccionar Load Balancer → Pestaña **"Certificates and ciphers"**
- Botón **"Add certificate"**

**Opciones disponibles en la interfaz**:
1. **Certificate name**: Nombre del certificado (ej: `carlosamieva-cert`)
2. **Specify SSL certificate**: 
   - Opción 1: "Choose SSL certificate file" (subir archivo)
   - Opción 2: "Paste SSL certificate" (pegar contenido) ✅ **Método usado**
   - **Formato requerido**: PEM (`.pem`, `.cer`, o `.crt`)
   - **Requisito**: Certificado debe estar firmado
3. **Specify CA certificate**: Toggle opcional para certificado CA
4. **Specify private key**: Toggle opcional para clave privada

**Proceso seguido**:
- ✅ Certificado pegado directamente en la consola web de Oracle Cloud
- ✅ **Archivo usado**: `/etc/letsencrypt/live/followup.fit/fullchain.pem`
  - Este archivo contiene el certificado + cadena intermedia (lo necesario para el Load Balancer)
  - Es un symlink a `../../archive/followup.fit/fullchain1.pem`
- ⚠️ Toggles activados: No confirmado (probablemente solo el certificado SSL, sin CA ni private key)

**Archivos disponibles en el servidor**:
- `cert.pem` → Solo el certificado (sin cadena intermedia)
- `chain.pem` → Solo la cadena intermedia
- `fullchain.pem` → Certificado + cadena intermedia ✅ **Este es el correcto**
- `privkey.pem` → Clave privada (no se necesita para importar en LB)

---

## 🔄 PROCESO DE RENOVACIÓN MANUAL

**IMPORTANTE**: Las renovaciones automáticas están fallando. El certificado debe renovarse **manualmente** cada 3 meses (antes de la expiración).

### Paso 1: Renovar el Certificado en el Servidor

```bash
# 1. Conectar al servidor
ssh -i ~/.ssh/ssh-key-2025-08-21.key ubuntu@140.238.120.92

# 2. Renovar el certificado (usando método manual/standalone)
sudo certbot renew --force-renewal --standalone

# O si el método anterior falla, regenerar desde cero:
sudo certbot certonly --standalone -d followup.fit -d www.followup.fit
```

**Nota**: El método `--standalone` requiere que el puerto 80 esté libre. Si hay un servicio escuchando, detenerlo temporalmente o usar otro método de validación.

### Paso 2: Verificar el Nuevo Certificado

```bash
# Verificar que se renovó correctamente
sudo certbot certificates

# Ver el contenido del nuevo certificado
sudo cat /etc/letsencrypt/live/followup.fit/fullchain.pem
```

### Paso 3: Copiar el Contenido del Certificado

```bash
# Mostrar el contenido completo del certificado para copiar
sudo cat /etc/letsencrypt/live/followup.fit/fullchain.pem
```

**Copiar todo el contenido** desde `-----BEGIN CERTIFICATE-----` hasta `-----END CERTIFICATE-----` (incluye certificado + cadena intermedia).

### Paso 4: Importar en Oracle Cloud Load Balancer

1. **Acceder a la consola**:
   - Oracle Cloud Console → Networking → Load Balancers
   - Seleccionar `CarlosAmieva-LB`
   - Pestaña **"Certificates and ciphers"**

2. **Añadir nuevo certificado**:
   - Click en **"Add certificate"**
   - **Certificate name**: `carlosamieva-cert` (o nuevo nombre con fecha)
   - **Specify SSL certificate**: Seleccionar **"Paste SSL certificate"**
   - **Pegar el contenido** de `fullchain.pem` (copiado en paso 3)
   - Click en **"Add certificate"**

3. **Actualizar el Listener HTTPS**:
   - Ir a pestaña **"Listeners"**
   - Click en el listener `listener_lb_2025-0512-0852` (HTTPS, puerto 443)
   - Click en **"Edit"**
   - En **"Certificate name"**, seleccionar el nuevo certificado
   - Click en **"Save changes"**

4. **Verificar**:
   - Esperar unos minutos a que se propague
   - Verificar que `https://followup.fit/` funciona correctamente
   - Verificar fecha de expiración del certificado en el navegador

### Paso 5: Limpiar Certificados Antiguos (Opcional)

Una vez confirmado que el nuevo certificado funciona:

```bash
# En Oracle Cloud Console, eliminar certificados antiguos si es necesario
# (Mantener solo el certificado activo)
```

---

## ⚠️ PROBLEMAS CONOCIDOS Y SOLUCIONES

### Problema: Renovaciones Automáticas Fallan

**Causa**: Los certificados fueron generados con método `standalone` o `webroot` que requiere acceso directo al servidor, pero el tráfico ahora pasa por el Load Balancer.

**Solución**: Renovación manual siguiendo el proceso arriba.

### Problema: Certbot Renew Falla con "Connection Refused"

**Causa**: El puerto 80 está ocupado o el servidor no es accesible directamente.

**Solución**: 
- Detener temporalmente servicios en puerto 80
- O usar método de validación DNS: `sudo certbot certonly --manual --preferred-challenges dns -d followup.fit -d www.followup.fit`

### Problema: Certificado Expirado en Load Balancer

**Solución**: Seguir proceso de renovación manual (Paso 1-4 arriba).

---

## 📅 CALENDARIO DE RENOVACIÓN

**Frecuencia**: Cada 3 meses (certificados Let's Encrypt)

**Recomendación**: Renovar **1 mes antes** de la expiración para evitar interrupciones.

**Recordatorio**: Configurar alerta/recordatorio para renovar antes de:
- Fecha actual de expiración: 2025-08-10
- Próxima renovación recomendada: **Julio 2025**

---

## 📝 Notas

- El certificado en el Load Balancer puede estar activo aunque los del servidor estén expirados
- Siempre verificar la fecha de expiración del certificado activo en el navegador
- Mantener una copia de seguridad del certificado y clave privada (en lugar seguro)

