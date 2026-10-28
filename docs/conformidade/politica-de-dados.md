# Política de dados

## Regra central

**Fatura real nunca entra no Git.** Uma fatura tem nome, endereço e número da instalação. No repositório só entram faturas **sintéticas** ou **anonimizadas**.

## O que pode e o que não pode

| Item | No repositório? |
|---|---|
| Fatura real (PDF, foto, texto) | **Não** |
| Notas brutas de entrevista | **Não** |
| Termos de consentimento | **Não** |
| Fatura sintética gerada pelo projeto | Sim, em `dados/benchmark/sinteticas/` |
| Síntese anonimizada de entrevistas | Sim, em `docs/` |
| Capturas de tela da documentação | Sim, em `docs/assets/` |
| Segredos, tokens e `.env` | **Não** (use `.env.example`) |

## Barreiras automáticas

1. **Hook de pre-commit** bloqueia PDF e imagens (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.heic`, `.heif`, `.webp`, `.bmp`, `.tif`, `.tiff`, `.gif`) fora de `docs/assets/` e de `dados/benchmark/sinteticas/`.
2. **O CI repete essa checagem** em todo PR e em todo push (vale mesmo para quem não instalou o hook ou usou `--no-verify`). O **gitleaks** também roda no pre-commit e em todo PR.
3. **`.gitignore`** ignora `.env`, `.heic` e pastas de notas brutas.
4. **Revisão:** todo PR é conferido pelo par de revisão, com atenção a arquivos de dados.

!!! danger "Se uma fatura real for commitada"
    Avise o Tech Lead imediatamente. Apagar o arquivo em um novo commit não remove o histórico: é preciso reescrever o histórico e avisar quem já clonou. Como o repositório é público, trate como vazamento. O procedimento detalhado está em `.github/SECURITY.md`.

## Onde ficam as faturas reais

TODO: local seguro combinado pelo time, fora do Git, com acesso restrito.
