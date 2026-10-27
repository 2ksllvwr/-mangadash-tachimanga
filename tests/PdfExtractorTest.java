import eu.kanade.tachiyomi.extension.pt.mangadash.PdfImageExtractor;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.DeflaterOutputStream;

/** Regression tests for extraction, deliberately run without java.desktop or Android. */
public final class PdfExtractorTest {
    private static byte[] ascii(String s) throws Exception { return s.getBytes("ISO-8859-1"); }
    private static byte[] stream(String dictionary, byte[] bytes) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(ascii("<< " + dictionary + " /Length " + bytes.length + " >>\nstream\n"));
        out.write(bytes); out.write(ascii("\nendstream")); return out.toByteArray();
    }
    private static byte[] pdf(byte[] first, byte[] second, String firstCommand, boolean flate) throws Exception {
        List<byte[]> objects = new ArrayList<>();
        objects.add(ascii("<< /Type /Catalog /Pages 2 0 R >>"));
        objects.add(ascii("<< /Type /Pages /Count 2 /Kids [3 0 R 5 0 R] /Resources 4 0 R /MediaBox [0 0 2 3] >>"));
        objects.add(ascii("<< /Type /Page /Parent 2 0 R /Contents 6 0 R >>"));
        objects.add(ascii("<< /XObject << /First 7 0 R /Second 8 0 R /Unused 9 0 R >> >>"));
        objects.add(ascii("<< /Type /Page /Parent 2 0 R /Contents 10 0 R >>"));
        objects.add(stream("", ascii(firstCommand)));
        String common = "/Type /XObject /Subtype /Image /Width 2 /Height 3 /ColorSpace /DeviceRGB /BitsPerComponent 8 ";
        objects.add(stream(common + (flate ? "/Filter /FlateDecode /DecodeParms << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns 2 >>" : "/Filter /DCTDecode"), first));
        objects.add(stream(common + "/Filter /DCTDecode", second));
        objects.add(stream(common + "/Filter /DCTDecode", first));
        objects.add(stream("", ascii("q 2 0 0 3 0 0 cm /First Do Q")));
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(ascii("%PDF-1.4\n"));
        List<Integer> offsets = new ArrayList<>();
        for (int i=0;i<objects.size();i++) {
            offsets.add(out.size()); out.write(ascii((i+1)+" 0 obj\n"));
            out.write(objects.get(i)); out.write(ascii("\nendobj\n"));
        }
        int xref=out.size(); out.write(ascii("xref\n0 "+(objects.size()+1)+"\n0000000000 65535 f \n"));
        for(int offset: offsets) out.write(ascii(String.format(Locale.ROOT,"%010d 00000 n \n",offset)));
        out.write(ascii("trailer\n<< /Size "+(objects.size()+1)+" /Root 1 0 R >>\nstartxref\n"+xref+"\n%%EOF\n"));
        return out.toByteArray();
    }
    private static void check(boolean result, String message) { if(!result) throw new AssertionError(message); }
    public static void main(String[] args) throws Exception {
        for(String unavailable: new String[]{"android.graphics.pdf.PdfRenderer", "java.awt.image.BufferedImage", "javax.imageio.ImageIO"}) {
            try { Class.forName(unavailable); throw new AssertionError(unavailable+" unexpectedly available"); }
            catch(ClassNotFoundException expected) { }
        }
        Path fixtures=Paths.get(args[0]);
        byte[] red=Files.readAllBytes(fixtures.resolve("red.jpg"));
        byte[] blue=Files.readAllBytes(fixtures.resolve("blue.jpg"));
        List<PdfImageExtractor.Image> pages=PdfImageExtractor.extract(new ByteArrayInputStream(pdf(red,blue,"q 2 0 0 3 0 0 cm /Second Do Q",false)));
        check(pages.size()==2,"Shared resources must not duplicate pages");
        check(Arrays.equals(pages.get(0).data,blue),"Page order must follow content operators");
        check(Arrays.equals(pages.get(1).data,red),"Second page must keep original JPEG bytes");
        check("image/jpeg".equals(pages.get(0).mimeType),"JPEG content type");
        ByteArrayOutputStream flate=new ByteArrayOutputStream();
        try(DeflaterOutputStream zipped=new DeflaterOutputStream(flate)) {
            for(int y=0;y<3;y++) zipped.write(new byte[]{0,(byte)255,0,0,(byte)255,0,0});
        }
        pages=PdfImageExtractor.extract(new ByteArrayInputStream(pdf(flate.toByteArray(),blue,"/First Do",true)));
        check("image/png".equals(pages.get(0).mimeType),"Flate image must become PNG");
        check(pages.get(0).data[0]==(byte)137,"PNG signature");
        if(args.length>1) Files.write(Paths.get(args[1]),pages.get(0).data);
        try {
            PdfImageExtractor.extract(new ByteArrayInputStream(pdf(red,blue,"/First Do /Second Do",false)));
            throw new AssertionError("Composite pages must not silently lose content");
        } catch(IOException expected) { check(expected.getMessage().contains("composição"),"Expected explicit unsupported-format message"); }
        System.out.println("PDF tests passed: ordered JPEG, shared resources, Flate/predictor PNG, unsupported-layout error; no Android/AWT/ImageIO.");
    }
}
