# Verificação do leitor PDF — 27/10/2026

## Falha observada

A captura do Tachimanga no iOS informa `Stub!` com `src: chapter-details`.
A versão 1.4.2 já usava `HttpSource`/API 1.4, mas mantinha o leitor Android
`PdfRenderer` e `ParcelFileDescriptor`. A versão 1.4.3 substitui esse caminho por
extração de imagens em Java e cache de capítulos em memória.

## Testes do novo leitor

O código real de extração foi compilado e executado com
`--limit-modules java.base,java.logging,java.xml`. Os testes confirmam que
`PdfRenderer`, `BufferedImage` e `ImageIO` não estão disponíveis nesse ambiente.

- Um PDF sintético com recursos compartilhados mantém a ordem das imagens
  conforme os comandos de cada página, sem duplicar imagens não utilizadas.
- Os JPEGs extraídos permanecem idênticos aos dados originais.
- Uma imagem Flate com predictor PNG é convertida em um PNG válido.
- Uma página com duas imagens produz um erro explícito de composição não
  suportada, evitando descartar parte do conteúdo.
- Um capítulo público real do MangaDash, Dandadan 249, com PDF de 27.171.655 bytes,
  resultou em 19 JPEGs de 1490 × 2100. Uma leitura independente com PyMuPDF
  confirmou os hashes de todas as 19 imagens e sua ordem no PDF.

Os arquivos do capítulo real são dados temporários de teste e não são
redistribuídos neste repositório. Os fixtures publicados são imagens sintéticas.

## Verificação de publicação

- `assembleRelease`, `lintRelease` e os testes do JAR otimizado passaram no GitHub Actions.
- O JAR assinado passou novamente nos testes sem Android/AWT/ImageIO e extraiu
  as 19 páginas reais com hashes iguais aos da leitura independente.
- O PNG produzido pelo JAR assinado foi decodificado separadamente: 2 × 3 pixels,
  todos RGB (255, 0, 0), conforme o fixture.
- As assinaturas do JAR e APK foram verificadas; o certificado continua igual ao
  da versão 1.4.2. Os hashes estão em `release.json` e `SHA256SUMS`.
- Os 15 testes do repositório passaram.
- O descritor protobuf oficial confirmou equivalência exata entre `index.pb` e
  `index.json`, incluindo versão 1.4.3 e identidade de fonte de 64 bits.
- A compilação está em
  https://github.com/2ksllvwr/-mangadash-tachimanga/actions/runs/40600980905
- `provenance.json` registra a origem e o commit utilizados.

## Limites

O aplicativo Tachimanga não foi executado em um iPhone/iPad nesta sessão.
Os testes sem Android verificam a extração, mas não simulam a máquina virtual
Java, o instalador ou o cache de páginas do Tachimanga. O teste final dentro do
aplicativo depende do usuário.

O leitor aceita PDFs baseados em uma imagem por página. Formatos vetoriais,
imagens com composição ou codecs não suportados pedem abertura no Web View.
As condições de acesso do MangaDash continuam valendo. Não há garantia de
leitura de todos os PDFs ou de acesso a todo o acervo da plataforma.
