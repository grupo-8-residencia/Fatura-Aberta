# Tarifas B1 — Neoenergia Brasília

Fonte: https://portalrelatorios.aneel.gov.br/luznatarifa/basestarifas

## Reproduzir
1. Abrir o relatório oficial ANEEL Luz na Tarifa / Bases Tarifárias.
2. Filtrar **Sigla = Neoenergia Brasília**, **Subgrupo = B1**, **Modalidade = Convencional**, **Classe = Residencial**, **Ano/Mês = 2026**; manter as subclasses necessárias e registrar demais filtros.
3. Na tabela, selecionar **Exportar dados → Dados resumidos → Excel (.xlsx)**. Se houver CSV disponível, ele também pode ser utilizado, mas não é obrigatório para esta entrega.
4. Salvar o arquivo em `dados/tarifas/` e atualizar `proveniencia.json` com data real da obtenção, nome do arquivo, URL e hash SHA-256.
5. Validar as colunas `Sigla`, `Resolução ANEEL`, `Início Vigência`, `Fim Vigência`, `Base Tarifária`, `Subgrupo`, `Modalidade`, `Classe`, `Subclasse`, `Unidade`, `TUSD`, `TE`.
6. Conferir a resolução, o período e a subclasse antes de usar qualquer tarifa. Os valores são em R$/MWh; para R$/kWh, dividir por 1000.

## Integridade
Em PowerShell: `Get-FileHash .\aneel_neoenergia_brasilia_b1_2026.xlsx -Algorithm SHA256`

SHA-256 do arquivo entregue: `38f66a3d805f317b6f9ec39c831af90da28f864acc77800f8c88d4ec130c16e4`

## Limitações
Este é um recorte exportado do Power BI, não o dump completo da base. A data de download foi confirmada pela responsável (29/10/2026); a consulta pode mudar ao longo do tempo. A tarifa de bandeira não foi validada neste arquivo. Não usar sem conferir vigência, subclasse e eventual regra de desconto.
