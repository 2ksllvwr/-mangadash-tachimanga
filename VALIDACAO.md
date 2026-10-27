# Verificação da correção — 27/10/2026

## Problema observado

O usuário relatou “Stub!” no Tachimanga após instalar MangaDash 1.6.0.
Essa versão usa a API nova `KeiSource`. A correção recompila o módulo legado
`HttpSource`/1.4, com a versão pessoal 1.4.2.

## Verificado

- Compilação `assembleRelease` e `lintRelease` passaram no GitHub Actions.
- Os metadados gerados declaram versão 1.4.2, API 1.4, pacote
  `eu.kanade.tachiyomi.extension.pt.mangadash` e fonte `4579000402227688678`.
- O JAR contém os métodos legados de catálogo, busca, detalhes, capítulos e páginas,
  sem dependência da classe `keiyoushi.source.KeiSource`.
- As assinaturas finais do JAR e APK foram verificadas com jarsigner e apksigner.
- O certificado do APK corresponde ao certificado público deste repositório.
- 13 testes automatizados passaram.
- Um leitor protobuf independente, usando o descritor oficial, confirmou que
  `index.pb` corresponde exatamente a `index.json`.
- A geração dos índices é determinística e não baixa novas versões do upstream.
- Os hashes dos arquivos assinados estão registrados em `release.json` e `SHA256SUMS`.
- As verificações anteriores da API pública do site responderam com busca e
  paginação de 374 obras em 16 páginas; esse total é uma observação daquele momento.

Compilação:
https://github.com/2ksllvwr/-mangadash-tachimanga/actions/runs/40584094683

## Limites

O Tachimanga não foi executado em um iPhone/iPad nesta sessão. A instalação e o
funcionamento dentro do aplicativo ainda precisam ser confirmados pelo usuário.
Os capítulos em PDF continuam dependendo do suporte a `PdfRenderer` no host.
A correção remove a dependência da API 1.6; não garante suporte a todas as APIs
Android utilizadas pelo código legado nem a leitura integral do acervo.
