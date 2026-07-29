# Career Dev Toolkit

## Goal

Criar um plugin local-first que transforme o contexto de trabalho já disponível no Cursor, Claude ou Codex em evidências de carreira estruturadas por STAR. O produto deve reduzir o esforço de manter um brag document sem transformar cada entrega em um formulário.

Este bootstrap valida a distribuição do mesmo contrato de skill nos três ecossistemas. Ele não representa o produto completo.

## Non-goals

- Implementar neste bootstrap o núcleo de persistência, sincronização com Google Docs ou Sheets, importação de PDF ou Career Canvas.
- Enviar threads completas ou conteúdo sensível para serviços externos.
- Inferir métricas, atribuição individual ou impacto como se fossem fatos.
- Avaliar promoção, nível ou performance do usuário.
- Suportar Ollama na primeira versão.

## Inputs

- Contexto da conversa atual no agente.
- Uma resposta opcional do usuário quando uma única lacuna muda materialmente a qualidade da evidência.
- No futuro, fontes locais autorizadas, PDF de perfil e integrações Google com escopo explícito.

## Outputs

- Rascunhos de entregas com Situation, Task, Action e Result.
- Lacunas de evidência visíveis, sem preenchimento inventado.
- Status verificável de compatibilidade por plataforma.

## Voice/Tone

Direto, calmo e específico. O produto ajuda o usuário a reconhecer o próprio impacto sem inflar linguagem ou transformar carreira em um jogo de pontuação.

## Open questions

- Qual será o formato canônico dos registros persistidos localmente?
- Como serão nomeados e versionados os adaptadores de provider e armazenamento?
- Qual política de consentimento governará exportações para Google Docs e Sheets?
- Como o judge adversarial combinará provedores sem expor dados além do necessário?
