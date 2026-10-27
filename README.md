# MangaDash para Tachimanga no iOS

Repositório pessoal gratuito de Gustavo, baseado no código Apache 2.0 do
[Keiyoushi](https://github.com/keiyoushi/extensions-source). Sem afiliação oficial
com MangaDash, Tachimanga ou Keiyoushi.

## Correção de capítulos PDF — versão 1.4.3

O erro informado pelo Tachimanga foi `Stub!` na etapa `chapter-details`.
A versão 1.4.2 já usava a API legada `HttpSource`, mas ainda tentava abrir PDFs
com `android.graphics.pdf.PdfRenderer`. A versão **1.4.3** substitui esse leitor
por extração das imagens do PDF em Java, sem Android Graphics, AWT ou ImageIO.

Um capítulo real com 19 páginas foi testado sem essas APIs. Uma segunda
biblioteca conferiu a ordem e os dados de todas as imagens, sem alterações.
O funcionamento dentro do Tachimanga no iPhone/iPad ainda precisa ser confirmado.

### Atualizar no iPhone

1. Na seção **Extensões** do Tachimanga, atualize MangaDash para **1.4.3**.
2. Confira a versão instalada e reabra o capítulo.
3. Caso o aplicativo reutilize páginas antigas, atualize a lista de páginas do
   capítulo ou remova somente o download desse capítulo antes de baixar novamente.

A assinatura e o identificador da fonte são os mesmos da versão 1.4.2; uma
atualização normal não exige remover o repositório nem apagar a biblioteca.
Se ainda estiver usando o pacote original 1.6.0, desinstale somente a extensão
MangaDash e adicione este repositório novamente antes de instalar a 1.4.3,
pois a chave de assinatura original era diferente.

## Endereço do repositório

```text
https://raw.githubusercontent.com/2ksllvwr/-mangadash-tachimanga/main/index.pb
```

No Tachimanga, use a seção **Extensões → Repositórios → Adicionar**.
Os nomes dos menus podem variar conforme a versão e o idioma do aplicativo.

Para instalação manual, use o botão **+** da seção Extensões e o arquivo
[JAR 1.4.3](https://raw.githubusercontent.com/2ksllvwr/-mangadash-tachimanga/main/jar/tachiyomi-pt.mangadash-v1.4.3.jar).
O iOS utiliza o JAR; o APK também é disponibilizado para outros clientes.

## Gratuidade e formatos

A extensão é gratuita e não inclui publicidade. Consulta a busca e a paginação
do site, sem limitar o catálogo a uma lista fixa. Nenhum mangá completo fica
hospedado neste repositório. Capítulos Premium, antecipados, removidos ou sujeitos
a login continuam com as condições da plataforma. Anúncios e funções pagas do
próprio Tachimanga são controlados pelo aplicativo.

Capítulos publicados como imagens continuam usando o caminho original. Para PDF,
o novo leitor extrai JPEGs e converte imagens RGB/cinza simples em PNG. Preserva
a ordem das páginas seguindo as instruções do documento, inclusive quando as
páginas compartilham o mesmo conjunto de imagens. Não renderiza documentos
vetoriais ou páginas com composição de várias imagens; nesses casos apresenta
um erro específico e orienta abrir o Web View. Mantém até dois capítulos em
memória, com limite de 96 MiB de imagens em cache. Não garante suporte a todo PDF
nem acesso integral ao acervo.

## Compilação e assinatura

- Base: `keiyoushi/extensions-source` no commit
  `d12e3b8a1eb5d7e5c7230f5b5b5854ba625a97dd`, API legada 1.4.
- O módulo em `source/mangadash/` contém as alterações publicadas.
- `tools/prepare_pdfbox.py` verifica os hashes do PDFBox/FontBox 2.0.37 e
  Commons Logging 1.2, prepara o parser e executa os testes sem Java Desktop.
- `source/headless-pdfbox/FilterFactory.java` retira a inicialização dos codecs
  gráficos de desktop. JPEGs são extraídos diretamente, sem esses codecs.
- O workflow **Compilar MangaDash para iOS** formata, compila, executa
  `lintRelease` e testa novamente o próprio JAR otimizado sem Android ou Java
  Desktop. As regras preservam as classes de logging carregadas por nome.
  Os artefatos de CI ainda não têm a assinatura de publicação.
- A assinatura final usa a mesma chave pessoal da versão 1.4.2. Somente o
  certificado público está no repositório.
- `provenance.json`, `source/build-info.json` e `release.json` registram a
  origem, a compilação, a identidade da fonte e os hashes dos arquivos assinados.

## Verificação

```bash
python3 -m unittest discover -s tests -v
python3 scripts/sync.py
python3 tools/prepare_pdfbox.py --output source/mangadash/libs
```

Os dois primeiros comandos exigem apenas Python 3.11+. O último também exige
JDK 11+ e acesso ao Maven Central. Seus testes executam Java com
`--limit-modules java.base,java.logging,java.xml`, tornando Android, AWT e ImageIO
indisponíveis. Testam ordem de páginas, recursos compartilhados, JPEG, PNG com
predictor e rejeição explícita de composição não suportada.

Os testes do repositório verificam versões, hashes, assinaturas presentes,
identidade de 64 bits, índices, métodos legados, licenças e ausência do antigo
leitor Android no JAR. As assinaturas criptográficas são conferidas separadamente
com `jarsigner` e `apksigner` antes de publicar.

O workflow **Verificar MangaDash compatível** verifica os arquivos e gera índices
diariamente. Mantém a API 1.4 e não baixa novas versões do upstream automaticamente.
`index.pb` é protobuf comprimido com gzip, conforme `schema/index.proto`.

## Licença

Apache 2.0: veja `LICENSE`, `NOTICE` e `source/mangadash/assets/licenses/`.

Documentação do Tachimanga:
[extensões](https://tachimanga.app/help/guides/extensions.html) e
[repositórios](https://tachimanga.app/help/guides/repositories.html).
