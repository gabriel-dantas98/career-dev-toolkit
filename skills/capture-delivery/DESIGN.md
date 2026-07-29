# Capture Delivery

## Goal

Extrair do contexto atual uma ou mais entregas úteis e organizá-las como rascunhos STAR, pedindo o mínimo possível ao usuário.

## Non-goals

- Avaliar promoção ou senioridade.
- Inventar métricas, escopo ou atribuição.
- Persistir, sincronizar ou enviar conteúdo para serviços externos.
- Contornar validações de privacidade.

## Inputs

- A thread atual.
- No máximo uma resposta opcional quando ela melhorar materialmente a atribuição ou o resultado.

## Outputs

- Um ou mais registros com Situation, Task, Action e Result.
- Campos ausentes marcados como lacunas de evidência.
- Bloqueio explícito quando o conteúdo contém dados sensíveis óbvios.

## Voice/Tone

Conciso, calmo e específico. O texto deve soar como uma autoavaliação honesta, não como propaganda.

## Open questions

- Como os futuros adaptadores de provider receberão apenas o contexto mínimo?
- Qual contrato será usado pelo armazenamento local?
