# ADR-010 — Fail-closed, sem modo leniente

**Decisão.** Indicador desconhecido, versão incompatível, unidade divergente, denominador ausente, valor fora de faixa ou evidência insegura **recusam a montagem inteira**. Não existe flag para "montar assim mesmo".

**Por quê.** Um resultado montado sobre fato irregular é pior que resultado nenhum: ele **parece confiável**. E um modo leniente seria um caminho pouco testado que acabaria ligado em produção "temporariamente".

**Consequência de desenho.** Não existe "indicador excluído" no resultado público — todo indicador que os fatos trouxeram está lá; o que varia é o **estado** de cada um. Por isso `Partiality` tem `complete` + `reasons` e não uma lista de exclusões: a lista seria sempre vazia, e campo sempre vazio mente sobre existir uma possibilidade.

**Onde a incompatibilidade de versão aparece.** Como **recusa tipada** (`unsupported_measurement_version`), não como estado publicável. É um desvio deliberado da leitura literal de "a estrutura deve distinguir incompatibilidade de versão": preferimos não publicar a publicar um documento cuja semântica ninguém garante. Registrado aqui para ser revisto se a integração provar que o desvio custa caro.
