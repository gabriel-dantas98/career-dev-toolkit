# Capture Delivery

## Goal

Extrair do contexto atual uma ou mais entregas úteis e projetá-las como rascunhos do schema de bragdoc do CareerOS, preservando STAR, evidências e lacunas sem inventar impacto.

## Non-goals

- Avaliar promoção ou senioridade.
- Inventar métricas, impacto, escopo, causalidade, datas ou atribuição.
- Persistir, sincronizar ou enviar conteúdo para serviços externos.
- Contornar validações de privacidade.
- Implementar normalização ou regras do schema dentro da skill.

## Inputs

- A thread atual.
- Apenas o menor trecho necessário enviado ao comando compartilhado do CareerOS.
- No máximo uma resposta opcional quando ela melhorar materialmente a atribuição ou o resultado.

## Outputs

- Um ou mais rascunhos com `record_id`, `period`, `title`, `tags`, `context`, `confidence`, `situation`, `task`, `action`, `result`, `evidence` e `evidence_gaps`.
- Campos ausentes preservados em `evidence_gaps`.
- Bloqueio explícito quando o conteúdo contém dados sensíveis óbvios.
- Nenhuma persistência; a saída continua revisável e local.

## Voice/Tone

Conciso, calmo e específico. O texto deve soar como uma autoavaliação honesta, não como propaganda.

## Open questions

- Qual opção registrada do CLI aceitará um trecho delimitado sem expor o restante da thread?
