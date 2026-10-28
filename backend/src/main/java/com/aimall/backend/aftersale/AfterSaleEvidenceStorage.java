package com.aimall.backend.aftersale;

import com.aimall.backend.common.BizException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;
import javax.imageio.ImageIO;
import java.io.*;
import java.nio.file.*;
import java.util.*;

@Component
public class AfterSaleEvidenceStorage {
    private static final long MAX_BYTES=5L*1024*1024;
    private final Path root;
    public AfterSaleEvidenceStorage(@Value("${app.after-sale.evidence-dir:./data/after-sale-evidence}") String directory) { root=Path.of(directory).toAbsolutePath().normalize(); }
    public String save(Long userId, MultipartFile file) {
        if(file==null||file.isEmpty()||file.getSize()>MAX_BYTES)throw new BizException(2001,"凭证图片须为5MB以内的PNG或JPEG");
        try {
            byte[] bytes=file.getBytes();String format;
            try(var input=ImageIO.createImageInputStream(new ByteArrayInputStream(bytes))) {
                var readers=ImageIO.getImageReaders(input);if(!readers.hasNext())throw new BizException(2001,"无法识别图片格式");
                var reader=readers.next();try{reader.setInput(input);format=reader.getFormatName().toLowerCase(Locale.ROOT);if(!Set.of("png","jpeg","jpg").contains(format)||(long)reader.getWidth(0)*reader.getHeight(0)>30000000L)throw new BizException(2001,"仅支持PNG/JPEG且不超过3000万像素");}finally{reader.dispose();}
            }
            String token=UUID.randomUUID().toString().replace("-","")+("png".equals(format)?".png":".jpg");
            Path path=path(userId,token);Files.createDirectories(path.getParent());Files.write(path,bytes,StandardOpenOption.CREATE_NEW);return token;
        } catch(BizException e){throw e;}catch(IOException e){throw new BizException(5000,"凭证保存失败，请重试");}
    }
    private Path path(Long owner,String token) {
        if(owner==null||owner<=0||token==null||!token.matches("[a-f0-9]{32}\\.(png|jpg)"))throw new BizException(2001,"凭证标识无效");
        Path result=root.resolve(String.valueOf(owner)).resolve(token).normalize();if(!result.startsWith(root))throw new BizException(2003,"无权访问该文件");return result;
    }
    public void validate(Long owner,List<String> tokens) {for(String token:tokens)if(!Files.isRegularFile(path(owner,token)))throw new BizException(2001,"凭证不存在或不属于当前用户");}
    public byte[] read(Long owner,String token) {try {Path path=path(owner,token);if(!Files.isRegularFile(path)||Files.size(path)>MAX_BYTES)throw new BizException(2002,"凭证不存在");return Files.readAllBytes(path);}catch(IOException e){throw new BizException(5000,"凭证读取失败");}}
}
