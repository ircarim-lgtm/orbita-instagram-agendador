# Órbita Labs: publicação agendada no Instagram

Publica Reels automaticamente em **@orbita_labs_dev** pelo GitHub Actions, sem precisar do computador ligado.

## Como funciona
- `calendar.json` lista os posts: data/hora (`publish_at`), vídeo, título e legenda.
- O workflow `.github/workflows/instagram-schedule.yml` roda a cada 15 min, de 07:00 a 09:59 (Brasília), e publica o post do dia.
- Cada post publicado é registrado em `published.json`, para não repetir.
- Se um post passar de 6 horas do horário, ele **não** é publicado e o GitHub mostra um erro.

## Requisitos
- **Repositório público.** O Instagram baixa o vídeo por uma URL do GitHub (`raw.githubusercontent.com`), que só funciona em repositório público. O Secret continua protegido mesmo com o repositório público.
- Secret do repositório `INSTAGRAM_ACCESS_TOKEN` (Settings → Secrets and variables → Actions).
O token do Instagram vence em cerca de 60 dias: gere outro no painel da Meta (Casos de uso → Personalizar → Configuração da API com login do Instagram → Gerar token) e troque o Secret.

## Testar sem publicar
Actions → "Instagram - publicar posts agendados" → Run workflow, com **dry_run** marcado.

## Formato dos vídeos (importante)
Entregue em **9:16 (1080x1920)**, H.264, 30 fps. Se o vídeo original for 4:5 ou quadrado, coloque-o no **centro** de uma tela 9:16 com o fundo desfocado do próprio vídeo (assim nada é cortado na tela cheia de Reels, no feed 4:5 nem na grade 3:4 do perfil). Evite vídeos e imagens quadrados (1:1): a grade do perfil corta as laterais. Mantenha textos a pelo menos 60 px das laterais.

Comando para converter um vídeo 4:5 (1080x1350):
```
ffmpeg -i entrada.mp4 -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=38,eq=brightness=-0.12[bg];[0:v]scale=1080:1350[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]" -map "[v]" -c:v libx264 -crf 18 -r 30 -movflags +faststart saida.mp4
```

## Adicionar novos posts
1. Coloque o vídeo em `media/` (9:16, até ~90 s).
2. Acrescente um item em `calendar.json` com `id`, `publish_at` (ex.: `2026-10-17T07:00:00-03:00`), `title`, `video` e `caption`.

## Rodar no computador (opcional)
```
pip install requests python-dotenv
copy .env.example .env      (e cole o token no .env)
cd scripts
python publish_instagram.py --test
```
