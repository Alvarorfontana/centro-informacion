# Redacción automática · los 12 agentes

Corren solos en GitHub tres veces por día (ediciones de 6:40, 12:40 y 18:40 de Argentina) y dejan el menú del día y los
borradores en el Centro, en **Redacción automática**. Ningún agente publica: vos elegís qué pasa a la
Mesa de edición o al administrador del diario. El repositorio del diario no se toca.

## Lo único que hay que hacer una vez: la clave gratuita de IA

Sin clave ya funcionan los monitores, el jefe (por puntaje), las fuentes, las fotos y el enlazador.
Para que el redactor, el verificador, el titulador y el corrector escriban:

1. Entrá a https://aistudio.google.com/apikey con tu cuenta de Google y creá una clave.
2. En GitHub: Settings → Secrets and variables → Actions → New repository secret.
   Nombre `GEMINI_API_KEY`, valor: la clave.
3. Opcional, de respaldo: una clave de https://console.groq.com/keys con el nombre `GROQ_API_KEY`.
4. Actions → Redacción automática → Run workflow, para no esperar a la próxima vuelta.

No usa tu plan de Claude.

## Qué se puede cambiar sin tocar código

- `agentes/config.json`: prender o apagar cada agente (`"prendido": false`), cuántos temas por sección
  (`cupos`) y los lugares del monitor local.
- `agentes/instrucciones/*.md`: lo que se le pide a cada agente con IA y la guía de estilo del diario.
- `datos/ejes.json`: la agenda de la agencia (Gobierno y Milei, PJ y Kicillof, FMI, energía…).

## Los agentes

| # | Agente | Qué hace | IA |
|---|--------|----------|----|
| 1 | Monitor Argentina | Ordena las noticias del país por región y por cuántos medios las cuentan | no |
| 2 | Monitor local | Busca los lugares de la lista `local` | no |
| 3 | Monitor Mercosur | Brasil, Uruguay, Paraguay, Bolivia, Chile y el bloque | no |
| 4 | Monitor internacional | Lo más cubierto en el mundo | no |
| 5 | Jefe de redacción | Arma el menú del día con el porqué de cada tema | sí |
| 6 | Redactor | Borrador propio, con palabras propias y cada dato atribuido | sí |
| 7 | Fuentes y autores | Autor, fecha, agencias citadas y documentos oficiales de cada nota original | no |
| 8 | Verificador | Revisa que cada dato esté en las fuentes | sí |
| 9 | Fotos | Foto de cada medio con crédito y fotos libres de Wikimedia | no |
| 10 | Titulador | Tres títulos y dos bajadas | sí |
| 11 | Enlazador | Enlaces a notas anteriores del diario (rojo) y a las fuentes (azul) | no |
| 12 | Corrector de estilo | Pule el texto sin tocar los datos | sí |

Orden en que trabajan sobre cada tema: fuentes → redactor → verificador → corrector → titulador → fotos → enlazador.
De las notas originales solo se guardan datos (medio, autor, fecha, enlace), nunca su texto.
