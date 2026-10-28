# Quadro e roadmap

O planejamento vive no GitHub Project **[Fatura Aberta](https://github.com/orgs/grupo-8-residencia/projects/1)**. Todas as issues do `planejamento/issues.yaml` estão nele, com estes campos:

| Campo | Valores |
|---|---|
| **Status** | A fazer, Em andamento, Em revisão, Feito |
| **Frente** | F1 a F6 e transversal |
| **Sprint** | S1 a S7 |
| **Início** e **Entrega** | segunda e sexta da sprint (alimentam o Roadmap) |

## Views

- **Kanban:** quadro agrupado por Status. Arraste o cartão entre as colunas.
- **Roadmap:** linha do tempo das sprints, usando **Início** e **Entrega**, agrupada por Sprint.
- **Tabela:** todas as issues, para filtrar por frente, sprint ou pessoa.

!!! info "As views são criadas na interface"
    O GitHub não permite criar views por API, então elas são configuradas uma vez, no navegador. O passo a passo está nas notas do PR de criação do quadro e abaixo.

### Como configurar (uma vez, por quem administra a org)

1. Abra o Project. Na view padrão, renomeie para **Tabela**.
2. **New view** > **Board**, nome **Kanban**. Em *Column field*, escolha **Status**. Em *Fields*, deixe Frente, Sprint e Assignees visíveis.
3. **New view** > **Roadmap**, nome **Roadmap**. No menu da view, **Date fields**: *Start date* = **Início**, *Target date* = **Entrega**. **Group by** = Sprint. **Markers** = Milestones. **Zoom** = Month.
4. **Settings** > **Workflows**: ative *Item added to project* (Status = A fazer), *Item closed* e *Pull request merged* (Status = Feito) e *Auto-add to project* para o repositório (filtro `is:issue`).

## Como o time usa

1. Pegou uma issue? Mova para **Em andamento**.
2. Abriu o PR? Mova para **Em revisão**.
3. Fechou a issue (o `Closes #N` do PR faz isso)? O cartão vai para **Feito**.
