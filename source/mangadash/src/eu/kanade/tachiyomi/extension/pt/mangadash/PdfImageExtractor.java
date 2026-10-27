package eu.kanade.tachiyomi.extension.pt.mangadash;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.CRC32;
import java.util.zip.DeflaterOutputStream;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.filter.FilterFactory;
import org.apache.pdfbox.io.RandomAccessBuffer;
import org.apache.pdfbox.pdfparser.PDFParser;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/** Extracts image-based PDF pages without Android graphics, AWT or ImageIO. */
public final class PdfImageExtractor {
  private static final int MAX_BYTES = 96 * 1024 * 1024;
  private static final int MAX_PIXELS = 40 * 1024 * 1024;

  private PdfImageExtractor() {}

  public static final class Image {
    public final byte[] data;
    public final String mimeType;

    Image(byte[] data, String mimeType) {
      this.data = data;
      this.mimeType = mimeType;
    }
  }

  public static List<Image> extract(InputStream input) throws IOException {
    RandomAccessBuffer buffer = new RandomAccessBuffer(read(input, MAX_BYTES));
    try {
      PDFParser parser = new PDFParser(buffer);
      parser.parse();
      try (COSDocument document = parser.getDocument()) {
        COSDictionary catalog = document.getTrailer().getCOSDictionary(COSName.ROOT);
        if (catalog == null) throw new IOException("PDF sem catálogo de páginas");
        List<Image> result = new ArrayList<>();
        Map<COSStream, Image> cache = new IdentityHashMap<>();
        pages(catalog.getCOSDictionary(COSName.PAGES), null, result, cache, 0);
        if (result.isEmpty()) throw new IOException("PDF sem páginas com imagens");
        long total = 0;
        for (Image image : result) total += image.data.length;
        if (total > MAX_BYTES)
          throw new IOException("Capítulo muito grande para carregar na memória");
        return result;
      }
    } finally {
      buffer.close();
    }
  }

  private static void pages(
      COSDictionary node,
      COSDictionary inherited,
      List<Image> result,
      Map<COSStream, Image> cache,
      int depth)
      throws IOException {
    if (node == null || depth > 50) throw new IOException("Árvore de páginas inválida");
    COSDictionary resources = node.getCOSDictionary(COSName.RESOURCES);
    if (resources == null) resources = inherited;
    if (node.getInt(COSName.ROTATE, 0) % 360 != 0) {
      throw new IOException("PDF com página rotacionada: abra este capítulo no Web View");
    }
    if (COSName.PAGE.equals(node.getCOSName(COSName.TYPE))) {
      List<COSStream> images = new ArrayList<>();
      content(node.getDictionaryObject(COSName.CONTENTS), resources, images, 0);
      if (images.size() != 1) {
        throw new IOException(
            "PDF exige composição gráfica na página "
                + (result.size() + 1)
                + "; abra este capítulo no Web View");
      }
      COSStream stream = images.get(0);
      Image image = cache.get(stream);
      if (image == null) {
        image = image(stream);
        cache.put(stream, image);
      }
      result.add(image);
      return;
    }
    COSArray kids = node.getCOSArray(COSName.KIDS);
    if (kids == null) throw new IOException("PDF sem lista de páginas");
    for (int i = 0; i < kids.size(); i++) {
      COSBase child = kids.getObject(i);
      if (!(child instanceof COSDictionary)) throw new IOException("Página PDF inválida");
      pages((COSDictionary) child, resources, result, cache, depth + 1);
    }
  }

  private static void content(
      COSBase value, COSDictionary resources, List<COSStream> images, int depth)
      throws IOException {
    if (depth > 20) throw new IOException("PDF com formulários recursivos");
    if (value instanceof COSArray) {
      COSArray array = (COSArray) value;
      for (int i = 0; i < array.size(); i++) content(array.getObject(i), resources, images, depth);
      return;
    }
    if (!(value instanceof COSStream)) return;
    COSStream stream = (COSStream) value;
    byte[] commands;
    try (InputStream input = stream.createInputStream()) {
      commands = read(input, MAX_BYTES);
    }
    PDFStreamParser parser = new PDFStreamParser(commands);
    parser.parse();
    Object operand = null;
    for (Object token : parser.getTokens()) {
      if (token instanceof Operator) {
        String operation = ((Operator) token).getName();
        if ("BI".equals(operation)) throw new IOException("PDF com imagem inline não suportada");
        if ("Tj".equals(operation)
            || "TJ".equals(operation)
            || "'".equals(operation)
            || "\"".equals(operation)) {
          throw new IOException("PDF com texto vetorial: abra este capítulo no Web View");
        }
        if ("Do".equals(operation) && operand instanceof COSName && resources != null) {
          COSDictionary objects = resources.getCOSDictionary(COSName.XOBJECT);
          COSBase object = objects == null ? null : objects.getDictionaryObject((COSName) operand);
          if (object instanceof COSStream) {
            COSStream target = (COSStream) object;
            COSName subtype = target.getCOSName(COSName.SUBTYPE);
            if (COSName.IMAGE.equals(subtype)) images.add(target);
            else if (COSName.FORM.equals(subtype)) {
              COSDictionary formResources = target.getCOSDictionary(COSName.RESOURCES);
              content(target, formResources == null ? resources : formResources, images, depth + 1);
            }
          }
        }
        operand = null;
      } else operand = token;
    }
  }

  private static Image image(COSStream stream) throws IOException {
    COSBase filters = stream.getDictionaryObject(COSName.FILTER);
    List<String> names = new ArrayList<>();
    if (filters instanceof COSName) names.add(((COSName) filters).getName());
    if (filters instanceof COSArray) {
      COSArray array = (COSArray) filters;
      for (int i = 0; i < array.size(); i++) {
        if (array.getObject(i) instanceof COSName)
          names.add(((COSName) array.getObject(i)).getName());
      }
    }
    if (names.contains("DCTDecode") || names.contains("DCT")) {
      try (InputStream input = stream.createRawInputStream()) {
        byte[] jpeg = read(input, MAX_BYTES);
        for (int i = 0; i < names.size(); i++) {
          String filter = names.get(i);
          if ("DCTDecode".equals(filter) || "DCT".equals(filter)) break;
          ByteArrayOutputStream decoded = new ByteArrayOutputStream();
          FilterFactory.INSTANCE
              .getFilter(filter)
              .decode(new ByteArrayInputStream(jpeg), decoded, stream, i);
          jpeg = decoded.toByteArray();
          if (jpeg.length > MAX_BYTES) throw new IOException("Imagem PDF muito grande");
        }
        if (jpeg.length < 3 || (jpeg[0] & 255) != 255 || (jpeg[1] & 255) != 216) {
          throw new IOException("Imagem JPEG inválida no PDF");
        }
        return new Image(jpeg, "image/jpeg");
      }
    }
    for (String filter : names) {
      if (!Arrays.asList(
              "FlateDecode",
              "Fl",
              "ASCII85Decode",
              "A85",
              "ASCIIHexDecode",
              "AHx",
              "RunLengthDecode",
              "RL",
              "LZWDecode",
              "LZW")
          .contains(filter)) {
        throw new IOException("Compressão PDF não suportada: " + filter + "; abra no Web View");
      }
    }
    int width = stream.getInt(COSName.WIDTH);
    int height = stream.getInt(COSName.HEIGHT);
    int bits = stream.getInt(COSName.BITS_PER_COMPONENT, 8);
    if (width <= 0 || height <= 0 || (long) width * height > MAX_PIXELS)
      throw new IOException("Imagem PDF muito grande");
    COSBase space = stream.getDictionaryObject(COSName.COLORSPACE);
    if (space instanceof COSArray && COSName.ICCBASED.equals(((COSArray) space).getObject(0))) {
      COSBase profile = ((COSArray) space).getObject(1);
      int components =
          profile instanceof COSDictionary ? ((COSDictionary) profile).getInt(COSName.N) : 0;
      space = components == 1 ? COSName.DEVICEGRAY : components == 3 ? COSName.DEVICERGB : null;
    }
    int channels = COSName.DEVICEGRAY.equals(space) ? 1 : COSName.DEVICERGB.equals(space) ? 3 : 0;
    if (channels == 0
        || (bits != 8 && !(channels == 1 && bits == 1))
        || stream.getDictionaryObject(COSName.SMASK) != null) {
      throw new IOException("Formato de imagem PDF não suportado; abra este capítulo no Web View");
    }
    int stride = (int) (((long) width * channels * bits + 7) / 8);
    byte[] raw;
    try (InputStream input = stream.createInputStream()) {
      raw = read(input, MAX_BYTES);
    }
    if (raw.length != (long) stride * height)
      throw new IOException("Tamanho da imagem PDF inválido");
    COSArray decode = stream.getCOSArray(COSName.DECODE);
    if (decode != null) {
      for (int i = 0; i < decode.size(); i += 2) {
        if (((COSNumber) decode.getObject(i)).floatValue() != 0f
            || ((COSNumber) decode.getObject(i + 1)).floatValue() != 1f) {
          throw new IOException("Transformação de cores PDF não suportada; abra no Web View");
        }
      }
    }
    ByteArrayOutputStream compressed = new ByteArrayOutputStream();
    try (DeflaterOutputStream deflater = new DeflaterOutputStream(compressed)) {
      for (int y = 0; y < height; y++) {
        deflater.write(0);
        deflater.write(raw, y * stride, stride);
      }
    }
    ByteArrayOutputStream result = new ByteArrayOutputStream();
    DataOutputStream output = new DataOutputStream(result);
    output.write(new byte[] {(byte) 137, 80, 78, 71, 13, 10, 26, 10});
    ByteArrayOutputStream header = new ByteArrayOutputStream();
    DataOutputStream ihdr = new DataOutputStream(header);
    ihdr.writeInt(width);
    ihdr.writeInt(height);
    ihdr.writeByte(bits);
    ihdr.writeByte(channels == 1 ? 0 : 2);
    ihdr.write(new byte[] {0, 0, 0});
    chunk(output, "IHDR", header.toByteArray());
    chunk(output, "IDAT", compressed.toByteArray());
    chunk(output, "IEND", new byte[0]);
    return new Image(result.toByteArray(), "image/png");
  }

  private static void chunk(DataOutputStream output, String type, byte[] data) throws IOException {
    byte[] name = type.getBytes("US-ASCII");
    output.writeInt(data.length);
    output.write(name);
    output.write(data);
    CRC32 crc = new CRC32();
    crc.update(name);
    crc.update(data);
    output.writeInt((int) crc.getValue());
  }

  private static byte[] read(InputStream input, int limit) throws IOException {
    ByteArrayOutputStream output = new ByteArrayOutputStream();
    byte[] buffer = new byte[8192];
    int count;
    while ((count = input.read(buffer)) != -1) {
      if (output.size() > limit - count) throw new IOException("PDF excede o limite de memória");
      output.write(buffer, 0, count);
    }
    return output.toByteArray();
  }
}
