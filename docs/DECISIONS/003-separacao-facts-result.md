# ADR-003 — Contratos separados para entrada e saída

**Decisão.** `analysis-facts-v1` (interno) e `analysis-result-v1` (público) são modelos **diferentes**, com tradução explícita entre eles.

**Por quê.** Com um modelo só, todo campo interno novo no domínio vazaria para o público **por omissão** — bastaria alguém adicionar um campo ao produtor. Com dois, o vazamento exige que alguém escreva o campo do lado público, e um teste estrutural reprova quando isso acontece por engano.

**Custo aceito.** Tradução manual em `assemble.py`. É onde moram o mapeamento id interno → id público, a seleção de estado e a decisão do que fica retido — trabalho que precisaria existir de qualquer forma.
