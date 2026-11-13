# Relatório da S3 — B1, B2 e B3 (quatro testes)

> **RESULTADO PARCIAL.** Cobertura incompleta em: faturas/LLM. Não há recomendação final. Os números abaixo são dos itens já medidos.

## 1. Dados da rodada

- Data (UTC): 2026-11-13T12:14:46Z; commit `422005d`; temperatura 0.0.
- Gerador: `gpt-oss:20b` (digest `17052f91a42e`); juiz: `qwen3:14b` (digest `bdbd181c33f2`).
- Sementes: LLM 42, bootstrap 42 (B = 10.000).
- Hash do golden set: `87aae5275aad9c9f3a73ea4e33abe5dbea3cd6800431cf1ca094db32bd40f453`.

## 2. Cobertura por baseline

| Conjunto | Esperado | Concluídos | Completo |
|---|---|---|---|
| faturas/B1 | 200 | 200 | sim |
| perguntas/LLM | 120 | 111 | sim |
| faturas/LLM | 200 | 0 | **não** |
| perguntas/RAG | 120 | 120 | sim |
| perguntas/B2 | 120 | 109 | sim |
| faturas/B2 | 200 | 200 | sim |
| perguntas/B3 | 120 | 104 | sim |
| faturas/B3 | 200 | 200 | sim |

Uma pergunta com resposta inválida (JSON fora do esquema) conta como inválida, não como acerto nem como item ausente.

## 3. Perguntas (120)

| Teste | n | Acerto (IC 95%) | Inválidas | Viol. RF-15 | Cit. inventadas | Fora de vigência | Latência média |
|---|---|---|---|---|---|---|---|
| T1 LLM sem RAG | 120 | 13.3% [7.5%; 20.0%] | 9 | 7 | 0 | 0 | 24.143 s |
| T2 RAG extrativo sem LLM | 120 | 83.3% [76.7%; 90.0%] | 0 | 0 | 0 | 0 | 0.003 s |
| T3 LLM + RAG (B2) | 120 | 74.2% [65.8%; 81.7%] | 11 | 4 | 1 | 11 | 24.406 s |
| T4 LLM + RAG + vigência (B3) | 120 | 78.3% [70.8%; 85.8%] | 16 | 5 | 1 | 0 | 22.738 s |

Acerto por tipo de pergunta:

| Teste | normativa | vigencia | lacuna | fora_do_corpus |
|---|---|---|---|---|
| T1 LLM sem RAG | 8.2% | 25.0% | 33.3% | 60.0% |
| T2 RAG extrativo sem LLM | 88.7% | 91.7% | 50.0% | 0.0% |
| T3 LLM + RAG (B2) | 88.7% | 8.3% | 33.3% | 0.0% |
| T4 LLM + RAG + vigência (B3) | 88.7% | 50.0% | 33.3% | 0.0% |

McNemar (pareado, p exato):

| Par | Só o 2º acerta | Só o 1º acerta | p (exato) | Diferença a 5% |
|---|---|---|---|---|
| RAG × LLM | 90 | 6 | 2.5e-20 | sim |
| B2 × LLM | 80 | 7 | 8.3e-17 | sim |
| B3 × B2 | 6 | 1 | 0.12 | não |
| B3 × RAG | 11 | 17 | 0.34 | não |
| B2 × RAG | 12 | 23 | 0.09 | não |

Regra de escolha (congelada antes dos resultados): 0 inválidas e 0 violações do RF-15; maior acerto; empate (< 1 p.p.) vai para a menor latência. Elegíveis nas perguntas: RAG.
Escolhido nas perguntas: **RAG** (acerto 83.3%).

## 4. Faturas (200)

| Teste | n | Acerto (IC 95%) | Detecção | Falso alarme | Abstenções | Latência média |
|---|---|---|---|---|---|---|
| B1 motor determinístico | 200 | 100.0% [100.0%; 100.0%] | 100.0% | 0.0% | 0 | 0.0 s |
| T1 LLM sem RAG | — | **sem resultado (cobertura incompleta)** | — | — | — | — |
| T3 LLM + RAG (B2) | 200 | 79.0% [73.5%; 84.5%] | 67.0% | 9.7% | 0 | 54.964 s |
| T4 LLM + RAG + vigência (B3) | 200 | 53.5% [46.5%; 60.0%] | 99.0% | 0.0% | 93 | 67.324 s |

McNemar:

| Par | Só o 2º acerta | Só o 1º acerta | p (exato) | Diferença a 5% |
|---|---|---|---|---|
| B3 × B2 | 34 | 85 | 3.3e-06 | sim |
| B3 × B1 | 0 | 93 | 2e-28 | sim |

Elegíveis nas faturas: B1, B2, B3. Escolhido: **B1**.

## 5. Recomendação

**Sem recomendação final**: a cobertura exigida pelo protocolo não está completa. A leitura provisória acima não substitui a comparação dos quatro testes nas 200 faturas.

## 6. Limitações

- O gabarito das faturas vem do mesmo gerador sintético do B1; o 100% do B1 mostra consistência do motor, não desempenho em faturas reais. Nenhuma fatura real foi usada (LGPD).
- O B3 se abstém quando a evidência é insuficiente: nas faturas isso derruba o acerto e eleva a detecção. O custo de abstenção não entrou na regra de escolha.
- Respostas inválidas (JSON fora do esquema) tornam o LLM inelegível pela regra; foi mantida a regra.
- Determinismo do Ollama não é garantido bit a bit mesmo com temperatura 0; as chamadas ficam em cache.
- Os IC 95% são bootstrap sobre os itens do golden set, cujo gabarito ainda está em revisão humana (#32).
- O juiz automático ainda não foi calibrado contra duas pessoas (kappa pendente); nenhum veredito dele é usado como verdade.
