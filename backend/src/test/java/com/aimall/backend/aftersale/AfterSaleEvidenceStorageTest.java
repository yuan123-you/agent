package com.aimall.backend.aftersale;
import com.aimall.backend.common.BizException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.nio.file.Path;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
class AfterSaleEvidenceStorageTest {
 @TempDir Path directory;
 @Test void uploadValidatesContentNotJustAnExtensionAndNeverUsesOriginalFilename()throws Exception {
   var store=new AfterSaleEvidenceStorage(directory.toString());var output=new ByteArrayOutputStream();ImageIO.write(new BufferedImage(2,2,BufferedImage.TYPE_INT_RGB),"png",output);
   String token=store.save(7L,new MockMultipartFile("file","../../outside.png","image/png",output.toByteArray()));
   assertTrue(token.matches("[a-f0-9]{32}\\.png"));assertArrayEquals(output.toByteArray(),store.read(7L,token));store.validate(7L,List.of(token));
   assertThrows(BizException.class,()->store.validate(8L,List.of(token)));
   assertThrows(BizException.class,()->store.read(7L,"../../outside.png"));
   assertThrows(BizException.class,()->store.save(7L,new MockMultipartFile("file","fake.png","image/png","<svg onload='x'/>".getBytes())));
 }
}
