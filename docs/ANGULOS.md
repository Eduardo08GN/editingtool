# Mapa de ângulos: a regra da operação low ticket

Cada campanha sobe com **25 criativos**: 5 públicos × 5 ângulos. Cada público tem a própria
campanha **ABO 1-1-5** (1 campanha, 1 conjunto, 5 anúncios), com R$ 15 por conjunto.

## A regra por público (o `edt validar` confere)

| item | regra |
|---|---|
| criativos | 5, cada um com um ângulo diferente |
| tempo de narração | 2 × 20 s, 2 × 30 s, 1 × 40 s |
| preço | 2 falam o preço, 3 não falam |
| CTA | todos terminam com **"Clique em saiba mais e confira."** |
| ritmo | ~2,6 palavras/s em pt-BR (≈ 52 palavras para 20 s, 78 para 30 s, 104 para 40 s) |

## Formato do arquivo (o importador lê exatamente isto)

```
Público 1 - Religioso (copys escolhidas)

1.1 Padre (20 s, sem preço)
Padre, quantas famílias saem da missa sem saber ensinar a fé aos filhos pequenos? ... Clique em saiba mais e confira.

1.2 Pastor (31 s, com preço)
...
```

- O cabeçalho do criativo é `N.M Nome do ângulo (SEGUNDOS s, com|sem preço)`.
- A copy vem nas linhas seguintes e pode ocupar mais de uma linha.
- Escreva o preço por extenso ("dez reais"). O selo **SÓ R$ 10** entra sozinho quando a voz diz "reais".

## Como escrever ângulos que funcionam (o que o exemplo faz)

1. **Gancho com o público no vocativo**: "Padre, ...", "Vó, ...", "Paizão, ...". A pessoa se
   reconhece no primeiro segundo.
2. **Dor ou desejo específico desse público**: o pastor quer material para os pais da igreja,
   a mãe quer menos tela, a madrinha quer um presente que não seja roupinha.
3. **Produto concreto**: número (setenta cards), formato (desenho na frente, história e
   brincadeira no verso) e exemplos visuais (imitar os bichos da Arca, contar as estrelas de Abraão).
4. **Facilidade**: imprime, recorta, plastifica, cinco minutinhos.
5. **Preço como argumento** (só em 2 de 5): "custa só dez reais", "por dez reais".
6. **CTA fixo** no fim.

Exemplo completo: `campanhas/biblia-do-bebe/copys.txt`.
