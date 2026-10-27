# Verificação do pacote — 27/10/2026

Este relatório registra a verificação local realizada antes da publicação.

## Verificado

- 12 testes automatizados passaram, incluindo preservação do identificador de
  fonte de 64 bits, exclusão de outras extensões, proteção contra troca de
  assinatura e recusa de arquivos com SHA-256 incorreto.
- `index.pb` usa protobuf comprimido com gzip, conforme o projeto original.
  Uma leitura independente com o descritor protobuf oficial confirmou que
  seu conteúdo corresponde exatamente a `index.json`.
- A entrada MangaDash no protobuf foi preservada integralmente em relação ao
  upstream. O JAR e o APK não foram recompilados nem modificados.
- As somas SHA-256 dos dois arquivos coincidem com as publicadas no mesmo
  commit do índice original. Ambos são arquivos ZIP íntegros; o JAR contém
  seus arquivos originais de assinatura.
- O catálogo público respondeu nas páginas 1, 2 e 16. A API informou 374 obras,
  distribuídas em 16 páginas naquele momento. Esse total é uma observação do
  catálogo público, não uma garantia sobre todo o acervo da plataforma.
- A busca por Dandadan respondeu com um resultado.
- A página pública de um capítulo de Dandadan apresentou os dados do leitor
  esperados pela extensão. Uma leitura parcial de cinco bytes do arquivo
  indicado retornou HTTP 206, tipo `application/pdf` e o cabeçalho `%PDF-`.
  Nenhum capítulo completo foi incluído neste pacote.
- Uma segunda geração a partir do mesmo snapshot não alterou os arquivos.

## Limites da verificação

O Tachimanga não foi executado em um iPhone/iPad nesta sessão. Não foram
validadas instalação e leitura dentro do aplicativo, renderização de PDFs,
preferências, login nem funcionamento com todas as obras. O JAR original usa
a API Android `PdfRenderer`, cuja implementação no Tachimanga precisa ser
conferida na prática. A execução do workflow no GitHub é verificada separadamente na aba Actions.

O acesso a conteúdo que exija conta, idade habilitada ou assinatura segue as
condições do MangaDash. Recursos pagos e anúncios do próprio Tachimanga são
controlados pelo aplicativo.

## Proveniência

Extensão: MangaDash 1.6.0, idioma `pt-BR`.

Pacote: `eu.kanade.tachiyomi.extension.pt.mangadash`.

Fonte: `4579000402227688678`.

O commit do índice, links dos arquivos e hashes estão em `provenance.json`
e `SHA256SUMS`. O código-fonte correspondente está em:

https://github.com/keiyoushi/extensions-source/tree/e40e1b78f46baf5ef9dc68cb980f82c66766a211/src/pt/mangadash
